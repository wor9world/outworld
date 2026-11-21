"""Knowledge store: notes, FTS5 search (trigram), and the `knowledge` tool.

The same functions back `GET /api/knowledge` and the agent-callable tool, so there is
exactly one search implementation.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app import db

from .registry import register_tool

COLUMNS = "id, project_id, title, body, tags, created_at, updated_at"


def fts_phrase(query: str) -> str | None:
    """Trigram tokenizer needs at least 3 characters; otherwise fall back to LIKE."""
    text = " ".join(query.split())
    if len(text) < 3:
        return None
    return '"' + text.replace('"', " ") + '"'


def search(
    conn: sqlite3.Connection,
    query: str | None = None,
    project_id: str | None = None,
    limit: int = 50,
    snippets: bool = False,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 200))
    phrase = fts_phrase(query) if query else None
    if phrase is not None:
        extra = " AND k.project_id = ?" if project_id else ""
        params: list[Any] = [phrase]
        if project_id:
            params.append(project_id)
        params.append(limit)
        rows = conn.execute(
            "SELECT k.id, k.title, k.tags, k.project_id, k.updated_at,"
            " bm25(knowledge_fts) AS rank,"
            " snippet(knowledge_fts, 1, '<mark>', '</mark>', '…', 12) AS snippet"
            " FROM knowledge_fts JOIN knowledge k ON k.rowid = knowledge_fts.rowid"
            f" WHERE knowledge_fts MATCH ?{extra}"
            " ORDER BY rank LIMIT ?",
            params,
        ).fetchall()
    elif query:
        like = f"%{query.strip()}%"
        extra = " AND project_id = ?" if project_id else ""
        params = [like, like]
        if project_id:
            params.append(project_id)
        params.append(limit)
        rows = conn.execute(
            "SELECT id, title, tags, project_id, updated_at"
            " FROM knowledge"
            f" WHERE (title LIKE ? OR body LIKE ?){extra}"
            " ORDER BY updated_at DESC LIMIT ?",
            params,
        ).fetchall()
    else:
        extra = " WHERE project_id = ?" if project_id else ""
        params = [project_id] if project_id else []
        params.append(limit)
        rows = conn.execute(
            "SELECT id, title, tags, project_id, updated_at FROM knowledge"
            f"{extra} ORDER BY updated_at DESC LIMIT ?",
            params,
        ).fetchall()
    return db.to_dicts(rows)


def create(
    conn: sqlite3.Connection,
    title: str,
    body: str = "",
    tags: str = "",
    project_id: str | None = None,
) -> dict[str, Any]:
    note_id = db.new_id()
    now = db.now_iso()
    conn.execute(
        "INSERT INTO knowledge (id, project_id, title, body, tags, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (note_id, project_id, title.strip(), body, tags, now, now),
    )
    conn.commit()
    row = conn.execute(f"SELECT {COLUMNS} FROM knowledge WHERE id = ?", (note_id,)).fetchone()
    assert row is not None
    return dict(row)


def get(conn: sqlite3.Connection, note_id: str) -> dict[str, Any] | None:
    row = conn.execute(f"SELECT {COLUMNS} FROM knowledge WHERE id = ?", (note_id,)).fetchone()
    return dict(row) if row is not None else None


def update(
    conn: sqlite3.Connection,
    note_id: str,
    title: str | None = None,
    body: str | None = None,
    tags: str | None = None,
) -> dict[str, Any] | None:
    data: dict[str, Any] = {}
    if title is not None:
        data["title"] = title.strip()
    if body is not None:
        data["body"] = body
    if tags is not None:
        data["tags"] = tags
    if not data:
        return get(conn, note_id)
    data["updated_at"] = db.now_iso()
    columns = ", ".join(f"{key} = ?" for key in data)
    conn.execute(
        f"UPDATE knowledge SET {columns} WHERE id = ?",  # noqa: S608 - fixed keys
        (*data.values(), note_id),
    )
    conn.commit()
    return get(conn, note_id)


def delete(conn: sqlite3.Connection, note_id: str) -> bool:
    cursor = conn.execute("DELETE FROM knowledge WHERE id = ?", (note_id,))
    conn.commit()
    return cursor.rowcount > 0


@register_tool(name="knowledge", description="Create, read and search knowledge notes (FTS5)")
def run(
    op: str,
    id: str | None = None,
    title: str | None = None,
    body: str | None = None,
    tags: str | None = None,
    project_id: str | None = None,
    q: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    conn = db.connect()
    try:
        if op == "create":
            if not title:
                return {"ok": False, "data": None, "meta": {}, "error": "title_required"}
            return {"ok": True, "data": create(conn, title, body or "", tags or "", project_id),
                    "meta": {}, "error": None}
        if op == "get":
            note = get(conn, id or "")
            if note is None:
                return {"ok": False, "data": None, "meta": {}, "error": "not_found"}
            return {"ok": True, "data": note, "meta": {}, "error": None}
        if op == "search":
            hits = search(conn, q, project_id, limit, snippets=True)
            return {"ok": True, "data": {"hits": hits}, "meta": {}, "error": None}
        return {"ok": False, "data": None, "meta": {}, "error": f"unknown_op:{op}"}
    finally:
        conn.close()
