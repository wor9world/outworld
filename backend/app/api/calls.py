"""Audit log and approvals (SPEC §5.11 — backup is added in T21)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from tools import registry

from .. import db, sandbox
from .tools import audit

router = APIRouter()


class DecisionIn(BaseModel):
    decision: str


@router.get("/calls")
def list_calls(
    chat_id: str | None = None,
    limit: int = 50,
    conn: sqlite3.Connection = Depends(db.get_db),
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 200))
    sql = (
        "SELECT id, chat_id, run_id, tool, status, ms, created_at, error,"
        " substr(args_json, 1, 200) AS args_preview FROM tool_calls"
    )
    params: list[Any] = []
    if chat_id:
        sql += " WHERE chat_id = ?"
        params.append(chat_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    return db.to_dicts(conn.execute(sql, params).fetchall())


@router.post("/approvals/{token}")
def decide(
    token: str, body: DecisionIn, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict[str, Any]:
    if body.decision not in ("approve", "deny"):
        raise HTTPException(400, "decision must be approve or deny")
    try:
        status, row = sandbox.decide(conn, token, body.decision)
    except sandbox.SandboxError as exc:
        raise HTTPException(exc.status, exc.code) from None

    assert row is not None
    args = json.loads(row["args_json"])
    args["approved"] = status == "approved"

    started = time.perf_counter()
    if status == "approved":
        tool = registry.get_tool(row["tool"])
        result = tool(**args)
    else:
        result = {"ok": False, "data": None, "meta": {}, "error": "denied"}
    elapsed = int((time.perf_counter() - started) * 1000)

    call_id = audit(
        conn,
        row["tool"],
        args,
        result,
        "ok" if result.get("ok") else ("denied" if status == "denied" else "error"),
        elapsed,
    )
    return {"status": status, "call_id": call_id, "result": result}


@router.get("/backup")
def backup(conn: sqlite3.Connection = Depends(db.get_db)) -> FileResponse:
    """Consistent snapshot through the SQLite backup API (safe while WAL is active)."""
    stamp = time.strftime("%Y%m%d-%H%M")
    tmp_dir = Path(tempfile.mkdtemp(prefix="outworld-backup-"))
    target = tmp_dir / f"outworld-{stamp}.db"
    destination = sqlite3.connect(target)
    try:
        conn.backup(destination)
    finally:
        destination.close()
    return FileResponse(
        target,
        media_type="application/octet-stream",
        filename=target.name,
        background=BackgroundTask(lambda: __import__("shutil").rmtree(tmp_dir, ignore_errors=True)),
    )
