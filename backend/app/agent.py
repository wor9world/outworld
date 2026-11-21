"""The agent loop as a generator of SSE events.

Yielding events (instead of taking a callback) lets the HTTP layer stream them as they
are produced while the loop itself stays synchronous.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator
from typing import Any

from tools import registry

from . import config, llm, sandbox, toolcall
from .api.tools import audit

Event = tuple[str, dict[str, Any]]

SCHEMAS: dict[str, dict[str, Any]] = {
    "fs": {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["read", "write", "list", "patch"]},
            "path": {"type": "string"},
            "content": {"type": "string"},
            "old": {"type": "string"},
            "new": {"type": "string"},
        },
        "required": ["op", "path"],
    },
    "shell": {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "cwd": {"type": "string"},
            "timeout_s": {"type": "integer"},
        },
        "required": ["command"],
    },
    "code": {
        "type": "object",
        "properties": {
            "language": {"type": "string", "enum": ["python", "javascript"]},
            "source": {"type": "string"},
            "timeout_s": {"type": "integer"},
        },
        "required": ["language", "source"],
    },
    "search": {
        "type": "object",
        "properties": {
            "scope": {"type": "string", "enum": ["knowledge", "workspace", "web"]},
            "q": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["scope", "q"],
    },
    "astro": {
        "type": "object",
        "properties": {
            "birth_date": {"type": "string"},
            "birth_time": {"type": "string"},
            "location": {"type": "string"},
        },
        "required": ["birth_date"],
    },
    "calc": {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["eval", "solve"]},
            "expr": {"type": "string"},
            "var": {"type": "string"},
        },
        "required": ["expr"],
    },
    "z3": {"type": "object", "properties": {"smt2": {"type": "string"}}, "required": ["smt2"]},
    "knowledge": {"type": "object", "properties": {"op": {"type": "string"}}, "required": ["op"]},
    "memory": {"type": "object", "properties": {"op": {"type": "string"}}, "required": ["op"]},
    "project": {
        "type": "object",
        "properties": {"op": {"type": "string"}, "name": {"type": "string"}},
        "required": ["op"],
    },
    "planner": {"type": "object", "properties": {"goal": {"type": "string"}}, "required": ["goal"]},
}


def tool_catalogue() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description or name,
                "parameters": SCHEMAS.get(name, {"type": "object", "properties": {}}),
            },
        }
        for name, description in sorted(registry.public_tools().items())
    ]


def system_prompt(conn: sqlite3.Connection, project_id: str | None, hints: str = "") -> str:
    parts = [
        "You are Outworld, a local workbench. Answer in the user's language.",
        "Use a tool only when it makes the answer more accurate. Never invent file contents.",
    ]
    if project_id:
        row = conn.execute(
            "SELECT name, instructions FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if row is not None:
            parts.append(f"Project: {row['name']}")
            if row["instructions"]:
                parts.append("Project instructions:\n" + row["instructions"])
    if hints:
        parts.append(hints)
    return "\n\n".join(parts)


def wait_for_approval(conn: sqlite3.Connection, token: str) -> str:
    import time as clock

    deadline = clock.time() + sandbox.APPROVAL_TTL_S
    while clock.time() < deadline:
        row = sandbox.read_approval(conn, token)
        if row is None:
            return "expired"
        row = sandbox.expire_if_needed(conn, row)
        if row["status"] != "pending":
            return str(row["status"])
        clock.sleep(0.5)
    conn.execute("UPDATE approvals SET status = 'expired' WHERE token = ?", (token,))
    conn.commit()
    return "expired"


def execute_tool(
    conn: sqlite3.Connection, tool: str, args: dict[str, Any], run_id: str
) -> tuple[dict[str, Any], list[Event]]:
    events: list[Event] = [("tool", {"tool": tool, "args": args, "status": "running"})]
    started = time.perf_counter()

    def invoke(**extra: Any) -> dict[str, Any]:
        return toolcall.invoke(tool, args, **extra)

    result = invoke()
    if result.get("error") == "approval_required":
        token = sandbox.mint(conn, tool, args)
        events.append(("approval", {"token": token, "tool": tool, "args": args}))
        status = wait_for_approval(conn, token)
        result = invoke(approved=True) if status == "approved" else {
            "ok": False, "data": None, "meta": {}, "error": status
        }

    elapsed = int((time.perf_counter() - started) * 1000)
    outcome_status = "ok" if result.get("ok") else (
        "denied" if result.get("error") in {"denied", "expired"} else "error"
    )
    call_id = audit(conn, tool, args, result, outcome_status, elapsed, None, run_id)
    events.append(
        (
            "tool_result",
            {
                "call_id": call_id,
                "status": outcome_status,
                "ms": elapsed,
                "preview": json.dumps(result.get("data"), ensure_ascii=False)[:400],
            },
        )
    )
    return {"call_id": call_id, "result": result, "ms": elapsed}, events


def run(
    conn: sqlite3.Connection,
    provider: dict[str, Any],
    chat_id: str,
    run_id: str,
    user_text: str,
    project_id: str | None,
    hints: str,
) -> Iterator[Event]:
    """Yield events; ``StopIteration.value`` is the final assistant text."""
    history = conn.execute(
        "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT 20",
        (chat_id,),
    ).fetchall()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt(conn, project_id, hints)}
    ]
    for row in reversed(history):
        if row["role"] in ("user", "assistant") and row["content"]:
            messages.append({"role": row["role"], "content": row["content"]})
    if not messages or messages[-1].get("content") != user_text:
        messages.append({"role": "user", "content": user_text})

    tools = tool_catalogue()
    limit = int(config.load_settings().get("llm_max_iterations", 8))
    content = ""

    for _ in range(1, limit + 1):
        final: dict[str, Any] | None = None
        for kind, payload in llm.stream(provider, messages, tools):
            if kind == "delta":
                yield "delta", {"text": payload}
            else:
                final = payload
        if final is None:
            raise llm.LLMError("provider returned no final message")

        content = final.get("content") or content
        calls = final.get("tool_calls") or []
        if not calls:
            return content

        messages.append(
            {
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "id": call.get("id") or f"call_{index}",
                        "type": "function",
                        "function": {
                            "name": call.get("name", ""),
                            "arguments": call.get("arguments") or "{}",
                        },
                    }
                    for index, call in enumerate(calls)
                ],
            }
        )

        for index, call in enumerate(calls):
            name = str(call.get("name", ""))
            try:
                args = json.loads(call.get("arguments") or "{}")
                if not isinstance(args, dict):
                    raise ValueError("arguments must be an object")
            except (ValueError, json.JSONDecodeError):
                yield "tool_result", {"status": "error", "ms": 0, "preview": "bad_tool_args"}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or f"call_{index}",
                        "content": json.dumps({"ok": False, "error": "bad_tool_args"}),
                    }
                )
                continue

            outcome, events = execute_tool(conn, name, args, run_id)
            yield from events
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id") or f"call_{index}",
                    "content": json.dumps(
                        outcome["result"], ensure_ascii=False, default=str
                    )[:8000],
                }
            )

    raise llm.LLMError("max_iterations")
