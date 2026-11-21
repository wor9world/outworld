"""Tool catalogue and dispatch. Every call is audited in tool_calls (SPEC §7.10)."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from .. import config, db, locations, sandbox
from tools import registry

router = APIRouter()

REDACT = {"api_key", "password", "token"}

STATUS_BY_ERROR = {
    "outside_workspace": 403,
    "ambiguous_patch": 409,
    "approval_required": 409,
}


def redact(args: dict[str, Any]) -> dict[str, Any]:
    return {key: ("***" if key.lower() in REDACT else value) for key, value in args.items()}


def audit(
    conn: sqlite3.Connection,
    tool: str,
    args: dict[str, Any],
    result: dict[str, Any],
    status: str,
    elapsed_ms: int,
    chat_id: str | None = None,
    run_id: str | None = None,
) -> int:
    payload = json.dumps(result.get("data"), ensure_ascii=False, default=str)
    max_bytes = int(config.load_settings().get("max_output_bytes", 65536))
    truncated = payload.encode("utf-8")[: max_bytes // 8].decode("utf-8", errors="ignore")
    cursor = conn.execute(
        "INSERT INTO tool_calls (chat_id, run_id, tool, args_json, result_json, status,"
        " error, ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            chat_id,
            run_id,
            tool,
            json.dumps(redact(args), ensure_ascii=False, default=str),
            truncated,
            status,
            result.get("error"),
            elapsed_ms,
            db.now_iso(),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid or 0)


@router.get("/tools")
def list_tools() -> list[dict[str, Any]]:
    schemas = {
        "fs": {
            "op": "read|write|list|patch",
            "path": "string (relative to workspace)",
            "content": "string?",
            "old": "string?",
            "new": "string?",
        },
        "shell": {"command": "string", "cwd": "string?", "timeout_s": "int?"},
        "code": {"language": "python|javascript", "source": "string", "timeout_s": "int?"},
        "search": {"scope": "knowledge|workspace|web", "q": "string", "limit": "int?"},
        "astro": {
            "birth_date": "YYYY-MM-DD",
            "birth_time": "HH:MM?",
            "location": "string? | lat+lon",
            "systems": "list[str]?",
        },
        "calc": {"op": "eval|solve", "expr": "string", "var": "string?"},
        "z3": {"smt2": "string"},
        "knowledge": {"op": "create|search|get"},
        "memory": {"op": "search|save|forget"},
        "project": {"op": "scaffold|verify", "name": "string"},
        "planner": {"goal": "string"},
    }
    return [
        {"id": name, "description": description, "input_schema": schemas.get(name, {})}
        for name, description in sorted(registry.public_tools().items())
    ]


@router.post("/tools/{tool}")
async def run_tool(
    tool: str,
    request: Request,
    conn: sqlite3.Connection = Depends(db.get_db),
) -> JSONResponse:
    if tool not in registry.public_tools():
        raise HTTPException(404, "unknown tool")

    try:
        body: Any = await request.json()
    except ValueError:
        raise HTTPException(400, "expected a JSON body") from None
    if not isinstance(body, dict):
        raise HTTPException(400, "expected a JSON object")

    chat_id = body.pop("chat_id", None)
    run_id = body.pop("run_id", None)
    approval_token = body.pop("approval_token", None)
    if approval_token:
        body["approval_token"] = approval_token

    # astro.py is a copy and its built-in location table is not complete; fill the
    # coordinates here instead of editing the tool.
    if tool == "astro" and not body.get("lat") and body.get("location"):
        found = locations.resolve(str(body["location"]))
        if found is not None:
            body["lat"], body["lon"] = found[0], found[1]
            if not body.get("tz_name"):
                body["tz_name"] = found[2]

    started = time.perf_counter()
    try:
        result = registry.get_tool(registry.resolve(tool))(**body)
    except TypeError as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        result = {"ok": False, "data": None, "meta": {}, "error": f"bad_args:{exc}"}
        audit(conn, tool, body, result, "error", elapsed, chat_id, run_id)
        return JSONResponse(result, status_code=400)
    elapsed = int((time.perf_counter() - started) * 1000)

    ok = bool(result.get("ok"))
    if not ok and result.get("error") == "approval_required":
        token = sandbox.mint(conn, tool, body)
        result["approval_token"] = token
        result["message"] = "approval_required"
        result.setdefault("meta", {})["approval_token"] = token

    status = "ok" if ok else "error"
    if not ok and result.get("error") == "timeout":
        status = "timeout"
    if not ok and result.get("error") == "denied":
        status = "denied"
    audit(conn, tool, body, result, status, elapsed, chat_id, run_id)

    http_status = 200 if ok else STATUS_BY_ERROR.get(str(result.get("error")), 200)
    if isinstance(body.get("approval_token"), str) and not ok:
        http_status = STATUS_BY_ERROR.get(str(result.get("error")), 200)
    return JSONResponse(result, status_code=http_status)
