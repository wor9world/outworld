"""One chat turn: pipe first, then the agent. Shared by the JSON and SSE endpoints."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from . import agent, db, learning, llm, pipe

MAX_INTENT = 200
TITLE_CHARS = 48
PIPE_THRESHOLD = 0.6


def normalize_intent(message: str) -> str:
    return " ".join(message.split())[:MAX_INTENT]


def llm_enabled(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM providers WHERE enabled = 1 AND model <> ''"
    ).fetchone()
    return bool(row[0])


def enabled_providers(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM providers WHERE enabled = 1 AND model <> '' ORDER BY created_at"
    ).fetchall()
    return [dict(row) for row in rows]


def open_run(
    conn: sqlite3.Connection,
    chat_id: str,
    project_id: str | None,
    message: str,
    intent_source: str = "none",
    matched_rule: str | None = None,
) -> str:
    run_id = db.new_id()
    conn.execute(
        "INSERT INTO runs (id, chat_id, project_id, intent, intent_source, matched_rule,"
        " status, started_at) VALUES (?, ?, ?, ?, ?, ?, 'running', ?)",
        (run_id, chat_id, project_id, normalize_intent(message), intent_source, matched_rule,
         db.now_iso()),
    )
    conn.commit()
    return run_id


def close_run(
    conn: sqlite3.Connection,
    run_id: str,
    status: str,
    iterations: int = 0,
    tool_count: int = 0,
    tokens: int = 0,
) -> None:
    conn.execute(
        "UPDATE runs SET status = ?, iterations = ?, tool_count = ?, tokens = ?, ended_at = ?"
        " WHERE id = ?",
        (status, iterations, tool_count, tokens, db.now_iso(), run_id),
    )
    conn.commit()


def add_user_message(conn: sqlite3.Connection, chat_id: str, content: str) -> dict[str, Any]:
    now = db.now_iso()
    cursor = conn.execute(
        "INSERT INTO messages (chat_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
        (chat_id, content, now),
    )
    chat = conn.execute("SELECT title FROM chats WHERE id = ?", (chat_id,)).fetchone()
    if chat is not None and chat["title"] == "New chat":
        title = normalize_intent(content)[:TITLE_CHARS] or "New chat"
        conn.execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))
    conn.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (now, chat_id))
    conn.commit()
    return {
        "id": cursor.lastrowid,
        "chat_id": chat_id,
        "role": "user",
        "content": content,
        "meta_json": "{}",
        "created_at": now,
    }


def add_assistant_message(
    conn: sqlite3.Connection, chat_id: str, content: str, meta: dict[str, Any]
) -> dict[str, Any]:
    now = db.now_iso()
    meta_json = json.dumps(meta, ensure_ascii=False)
    cursor = conn.execute(
        "INSERT INTO messages (chat_id, role, content, meta_json, created_at)"
        " VALUES (?, 'assistant', ?, ?, ?)",
        (chat_id, content, meta_json, now),
    )
    conn.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (now, chat_id))
    conn.commit()
    return {
        "id": cursor.lastrowid,
        "chat_id": chat_id,
        "role": "assistant",
        "content": content,
        "meta_json": meta_json,
        "created_at": now,
    }


def decide(message: str) -> dict[str, Any]:
    """Pipe decision for this message."""
    routed = pipe.route(message)
    matched = bool(routed.get("intent")) and float(routed.get("confidence") or 0) >= PIPE_THRESHOLD
    return {"matched": matched, "route": routed}


def recall_hints(conn: sqlite3.Connection, message: str) -> tuple[str, list[str]]:
    patterns = learning.recall(conn, message)
    return learning.hints(patterns), [str(pattern["id"]) for pattern in patterns]


def finish_run(conn: sqlite3.Connection, run_id: str, pattern_ids: list[str]) -> None:
    """Distil a pattern from a successful run and count the ones that were injected."""
    learning.record_use(conn, pattern_ids)
    learning.distill(conn, run_id, set(pattern_ids))


def run_chat(conn: sqlite3.Connection, chat_id: str, content: str) -> dict[str, Any]:
    """Synchronous turn: pipe when it matches, otherwise report why there is no answer."""
    chat = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
    project_id = chat["project_id"] if chat is not None else None
    routed = decide(content)
    route = routed["route"]

    run_id = open_run(
        conn,
        chat_id,
        project_id,
        content,
        intent_source="pipe" if routed["matched"] else "none",
        matched_rule=route.get("rule_id") if routed["matched"] else None,
    )
    user_message = add_user_message(conn, chat_id, content)
    hint_text, pattern_ids = recall_hints(conn, content)

    if routed["matched"]:
        outcome = pipe.run(conn, content, chat_id, run_id)
        text = outcome.get("answer") or json.dumps(
            [step["result"] for step in outcome["results"]], ensure_ascii=False
        )[:2000]
        meta = {
            "intent": outcome["intent"],
            "tool_call_ids": [step["call_id"] for step in outcome["results"]],
            "warnings": [],
        }
        assistant = add_assistant_message(conn, chat_id, text, meta)
        close_run(
            conn,
            run_id,
            "ok" if not outcome.get("error") else "error",
            tool_count=len(outcome["results"]),
        )
        finish_run(conn, run_id, pattern_ids)
        return {
            "run_id": run_id,
            "intent": outcome["intent"],
            "user_message": user_message,
            "assistant_message": assistant,
            "warnings": [],
        }

    if not llm_enabled(conn):
        close_run(conn, run_id, "ok")
        finish_run(conn, run_id, pattern_ids)
        return {
            "run_id": run_id,
            "intent": None,
            "user_message": user_message,
            "assistant_message": None,
            "warnings": ["no_route"],
        }

    provider = enabled_providers(conn)[0]
    stream = agent.run(conn, provider, chat_id, run_id, content, project_id, hint_text)
    text = ""
    try:
        while True:
            next(stream)
    except StopIteration as stop:
        text = stop.value or ""

    meta = {"intent": None, "provider_id": provider["id"], "model": provider["model"],
            "warnings": []}
    assistant = add_assistant_message(conn, chat_id, text, meta)
    close_run(conn, run_id, "ok", iterations=1)
    finish_run(conn, run_id, pattern_ids)
    return {
        "run_id": run_id,
        "intent": None,
        "user_message": user_message,
        "assistant_message": assistant,
        "warnings": [],
    }


__all__ = [
    "add_assistant_message",
    "add_user_message",
    "close_run",
    "decide",
    "enabled_providers",
    "llm",
    "llm_enabled",
    "normalize_intent",
    "open_run",
    "run_chat",
]
