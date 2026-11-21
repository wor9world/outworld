"""Learning endpoints (SPEC §5.10)."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db, learning

router = APIRouter()


class FeedbackIn(BaseModel):
    verdict: str = Field(pattern="^(good|bad)$")
    note: str = ""


class PatternPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None


class PromoteIn(BaseModel):
    project_id: str


@router.get("/runs")
def list_runs(
    chat_id: str | None = None, limit: int = 50, conn: sqlite3.Connection = Depends(db.get_db)
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 200))
    sql = (
        "SELECT r.id, r.chat_id, r.intent, r.intent_source, r.matched_rule, r.status,"
        " r.tool_count, r.iterations, r.started_at, r.ended_at, f.verdict"
        " FROM runs r LEFT JOIN feedback f ON f.run_id = r.id"
    )
    params: list[Any] = []
    if chat_id:
        sql += " WHERE r.chat_id = ?"
        params.append(chat_id)
    sql += " ORDER BY r.started_at DESC LIMIT ?"
    params.append(limit)
    return db.to_dicts(conn.execute(sql, params).fetchall())


@router.get("/runs/{run_id}")
def get_run(run_id: str, conn: sqlite3.Connection = Depends(db.get_db)) -> dict[str, Any]:
    run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        raise HTTPException(404, "run not found")
    calls = db.to_dicts(
        conn.execute("SELECT * FROM tool_calls WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
    )
    feedback = conn.execute("SELECT * FROM feedback WHERE run_id = ?", (run_id,)).fetchone()
    return {"run": dict(run), "calls": calls, "feedback": dict(feedback) if feedback else None}


@router.post("/runs/{run_id}/feedback")
def post_feedback(
    run_id: str, body: FeedbackIn, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict[str, Any]:
    if conn.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone() is None:
        raise HTTPException(404, "run not found")
    return learning.feedback(conn, run_id, body.verdict, body.note)


@router.get("/patterns")
def list_patterns(
    q: str | None = None, limit: int = 50, conn: sqlite3.Connection = Depends(db.get_db)
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 200))
    if q:
        rows = learning.recall(conn, q, limit=limit)
    else:
        rows = db.to_dicts(
            conn.execute(
                "SELECT * FROM patterns ORDER BY success DESC, uses DESC LIMIT ?", (limit,)
            ).fetchall()
        )
    for row in rows:
        row["tool_chain"] = json.loads(row.get("tool_chain_json") or "[]")
        row["rate"] = round(row["success"] / max(row["uses"], 1), 3)
        row["enabled"] = bool(row["enabled"])
    return rows


@router.get("/patterns/{pattern_id}")
def get_pattern(pattern_id: str, conn: sqlite3.Connection = Depends(db.get_db)) -> dict[str, Any]:
    pattern = conn.execute("SELECT * FROM patterns WHERE id = ?", (pattern_id,)).fetchone()
    if pattern is None:
        raise HTTPException(404, "pattern not found")
    sample = conn.execute(
        "SELECT * FROM runs WHERE id = ?", (pattern["source_run_id"],)
    ).fetchone()
    return {"pattern": dict(pattern), "sample_run": dict(sample) if sample else None}


@router.patch("/patterns/{pattern_id}")
def patch_pattern(
    pattern_id: str, body: PatternPatch, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict[str, Any]:
    pattern = conn.execute("SELECT * FROM patterns WHERE id = ?", (pattern_id,)).fetchone()
    if pattern is None:
        raise HTTPException(404, "pattern not found")
    data: dict[str, Any] = body.model_dump(exclude_none=True)
    if "enabled" in data:
        data["enabled"] = int(bool(data["enabled"]))
    if data:
        columns = ", ".join(f"{key} = ?" for key in data)
        conn.execute(
            f"UPDATE patterns SET {columns} WHERE id = ?",
            (*data.values(), pattern_id),
        )
        conn.commit()
    return dict(conn.execute("SELECT * FROM patterns WHERE id = ?", (pattern_id,)).fetchone())


@router.delete("/patterns/{pattern_id}", status_code=204)
def delete_pattern(pattern_id: str, conn: sqlite3.Connection = Depends(db.get_db)):
    cursor = conn.execute("DELETE FROM patterns WHERE id = ?", (pattern_id,))
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(404, "pattern not found")
    return


@router.post("/patterns/{pattern_id}/promote")
def promote_pattern(
    pattern_id: str, body: PromoteIn, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict[str, Any]:
    try:
        instructions = learning.promote(conn, pattern_id, body.project_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc).strip("'")) from None
    return {"instructions": instructions}


@router.get("/learning/stats")
def learning_stats(conn: sqlite3.Connection = Depends(db.get_db)) -> dict[str, Any]:
    return learning.stats(conn)
