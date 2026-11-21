"""`memory` tool: the agent's handle on patterns."""

from __future__ import annotations

import json
from typing import Any

from app import db, learning

from .registry import register_tool


@register_tool(name="memory", description="Search, save or forget learned tool patterns")
def run(
    op: str,
    q: str | None = None,
    name: str | None = None,
    intent: str | None = None,
    tool_chain: list[str] | None = None,
) -> dict[str, Any]:
    conn = db.connect()
    try:
        if op == "search":
            if not q:
                return {"ok": False, "data": None, "meta": {}, "error": "query_required"}
            rows = learning.recall(conn, q, limit=5)
            return {"ok": True, "data": {"patterns": rows}, "meta": {}, "error": None}

        if op == "save":
            if not name or not intent or not tool_chain:
                return {"ok": False, "data": None, "meta": {}, "error": "name_intent_chain_required"}
            pattern_id = db.new_id()
            now = db.now_iso()
            conn.execute(
                "INSERT INTO patterns (id, project_id, name, intent, tool_chain_json,"
                " args_template_json, uses, success, last_used_at, source_run_id, enabled,"
                " created_at) VALUES (?, NULL, ?, ?, ?, '[]', 1, 1, ?, NULL, 1, ?)",
                (pattern_id, name, intent, json.dumps(tool_chain), now, now),
            )
            conn.commit()
            return {"ok": True, "data": {"id": pattern_id}, "meta": {}, "error": None}

        if op == "forget":
            if not name:
                return {"ok": False, "data": None, "meta": {}, "error": "name_required"}
            cursor = conn.execute("UPDATE patterns SET enabled = 0 WHERE name = ?", (name,))
            conn.commit()
            return {"ok": True, "data": {"disabled": cursor.rowcount}, "meta": {}, "error": None}

        return {"ok": False, "data": None, "meta": {}, "error": f"unknown_op:{op}"}
    finally:
        conn.close()
