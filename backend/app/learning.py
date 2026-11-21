"""Learning: runs become patterns, patterns become hints (SPEC §4.10-4.13).

Everything here is deterministic. No model is consulted at any step, so learning works
with zero providers configured.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from tools.knowledge import fts_phrase

from . import db

MAX_HINTS = 3
HINT_BUDGET = 600
MIN_TOOLS = 2


def _string_chain(calls: list[sqlite3.Row]) -> tuple[list[str], list[dict[str, Any]]]:
    chain: list[str] = []
    template: list[dict[str, Any]] = []
    for call in calls:
        tool = str(call["tool"])
        chain.append(tool)
        try:
            args = json.loads(call["args_json"])
        except (TypeError, json.JSONDecodeError):
            args = {}
        templated = {
            key: (f"{{{{{key}}}}}" if isinstance(value, str) and value else value)
            for key, value in (args or {}).items()
            if key not in {"approved", "chat_id", "run_id"}
        }
        template.append({"tool": tool, "args": templated})
    return chain, template


def distill(conn: sqlite3.Connection, run_id: str, injected: set[str] | None = None) -> dict[str, Any] | None:
    """Turn a successful multi-tool run into a pattern (upsert on intent + chain).

    ``injected`` holds the patterns that were already recalled for this run, so their
    ``uses`` counter is not incremented twice.
    """
    injected = injected or set()
    run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if run is None or run["status"] != "ok" or int(run["tool_count"]) < MIN_TOOLS:
        return None
    calls = conn.execute(
        "SELECT tool, args_json FROM tool_calls WHERE run_id = ? ORDER BY id", (run_id,)
    ).fetchall()
    if len(calls) < MIN_TOOLS:
        return None

    chain, template = _string_chain(calls)
    chain_json = json.dumps(chain)
    existing = conn.execute(
        "SELECT * FROM patterns WHERE intent = ? AND tool_chain_json = ?",
        (run["intent"], chain_json),
    ).fetchone()
    now = db.now_iso()
    if existing is not None:
        already_counted = existing["id"] in injected
        conn.execute(
            "UPDATE patterns SET uses = uses + ?, success = success + 1, last_used_at = ?"
            " WHERE id = ?",
            (0 if already_counted else 1, now, existing["id"]),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM patterns WHERE id = ?", (existing["id"],)).fetchone()
        return dict(row)

    pattern_id = db.new_id()
    name = " → ".join(chain)
    conn.execute(
        "INSERT INTO patterns (id, project_id, name, intent, tool_chain_json,"
        " args_template_json, uses, success, last_used_at, source_run_id, enabled, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?, 1, ?)",
        (
            pattern_id,
            run["project_id"],
            name,
            run["intent"],
            chain_json,
            json.dumps(template, ensure_ascii=False),
            now,
            run_id,
            now,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM patterns WHERE id = ?", (pattern_id,)).fetchone()
    return dict(row)


def recall(conn: sqlite3.Connection, message: str, limit: int = MAX_HINTS) -> list[dict[str, Any]]:
    """FTS5 match, then rank by success rate. Never returns patterns with zero successes."""
    phrase = fts_phrase(message)
    if phrase is None:
        return []
    rows = conn.execute(
        "SELECT p.*, bm25(pattern_fts) AS rank FROM pattern_fts"
        " JOIN patterns p ON p.rowid = pattern_fts.rowid"
        " WHERE pattern_fts MATCH ? AND p.enabled = 1 AND p.success > 0"
        " ORDER BY (p.success * 1.0 / MAX(p.uses, 1)) DESC, p.last_used_at DESC"
        " LIMIT ?",
        (phrase, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def hints(patterns: list[dict[str, Any]]) -> str:
    if not patterns:
        return ""
    lines = ["Known patterns for similar requests:"]
    budget = HINT_BUDGET - len(lines[0])
    for pattern in patterns:
        line = f"- {pattern['name']} ({pattern['success']}/{max(pattern['uses'], 1)})"
        if len(line) + 1 > budget:
            break
        lines.append(line)
        budget -= len(line) + 1
    return "\n".join(lines) if len(lines) > 1 else ""


def record_use(conn: sqlite3.Connection, pattern_ids: list[str]) -> None:
    if not pattern_ids:
        return
    now = db.now_iso()
    for pattern_id in pattern_ids:
        conn.execute(
            "UPDATE patterns SET uses = uses + 1, last_used_at = ? WHERE id = ?",
            (now, pattern_id),
        )
    conn.commit()


def feedback(conn: sqlite3.Connection, run_id: str, verdict: str, note: str = "") -> dict:
    conn.execute(
        "INSERT INTO feedback (run_id, verdict, note, created_at) VALUES (?, ?, ?, ?)"
        " ON CONFLICT(run_id) DO UPDATE SET verdict = excluded.verdict, note = excluded.note",
        (run_id, verdict, note, db.now_iso()),
    )
    delta = 1 if verdict == "good" else -1
    conn.execute(
        "UPDATE patterns SET success = MAX(success + ?, 0)"
        " WHERE source_run_id = ? OR intent = (SELECT intent FROM runs WHERE id = ?)",
        (delta, run_id, run_id),
    )
    conn.commit()
    return {"verdict": verdict}


def promote(conn: sqlite3.Connection, pattern_id: str, project_id: str) -> str:
    pattern = conn.execute("SELECT * FROM patterns WHERE id = ?", (pattern_id,)).fetchone()
    if pattern is None:
        raise KeyError("pattern not found")
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if project is None:
        raise KeyError("project not found")
    chain = json.loads(pattern["tool_chain_json"])
    bullet = f"- {pattern['name']}: {' → '.join(chain)}"
    instructions = (project["instructions"] or "").rstrip()
    if bullet in instructions:
        return instructions
    instructions = (instructions + "\n" + bullet).strip() if instructions else bullet
    conn.execute(
        "UPDATE projects SET instructions = ?, updated_at = ? WHERE id = ?",
        (instructions, db.now_iso(), project_id),
    )
    conn.commit()
    return instructions


def stats(conn: sqlite3.Connection) -> dict[str, Any]:
    runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    ok = conn.execute("SELECT COUNT(*) FROM runs WHERE status = 'ok'").fetchone()[0]
    pipe_runs = conn.execute(
        "SELECT COUNT(*) FROM runs WHERE intent_source = 'pipe'"
    ).fetchone()[0]
    patterns = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
    top = conn.execute(
        "SELECT name, uses, success FROM patterns ORDER BY success DESC, uses DESC LIMIT 3"
    ).fetchall()
    recalls = conn.execute(
        "SELECT COALESCE(SUM(uses), 0) FROM patterns WHERE last_used_at IS NOT NULL"
    ).fetchone()[0]
    return {
        "runs_total": runs,
        "ok_rate": round(ok / runs, 3) if runs else 0.0,
        "pipe_rate": round(pipe_runs / runs, 3) if runs else 0.0,
        "patterns_total": patterns,
        "top_patterns": [dict(row) for row in top],
        "recalls_24h": int(recalls),
    }
