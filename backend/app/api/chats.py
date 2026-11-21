"""Chats: create, list, read (paged), rename, delete."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db, runner
from .projects import valid_id

router = APIRouter()


class ChatIn(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class ChatPatch(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


def fetch_chat(conn: sqlite3.Connection, chat_id: str) -> sqlite3.Row:
    valid_id(chat_id)
    row = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "chat not found")
    return row


@router.get("/projects/{project_id}/chats")
def list_project_chats(
    project_id: str, conn: sqlite3.Connection = Depends(db.get_db)
) -> list[dict]:
    valid_id(project_id)
    rows = conn.execute(
        "SELECT id, title, updated_at,"
        " (SELECT COUNT(*) FROM messages m WHERE m.chat_id = c.id) AS message_count"
        " FROM chats c WHERE project_id = ? ORDER BY updated_at DESC",
        (project_id,),
    ).fetchall()
    return db.to_dicts(rows)


@router.post("/projects/{project_id}/chats", status_code=201)
def create_chat(
    project_id: str, body: ChatIn, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict:
    valid_id(project_id)
    if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
        raise HTTPException(404, "project not found")
    chat_id = db.new_id()
    now = db.now_iso()
    conn.execute(
        "INSERT INTO chats (id, project_id, title, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (chat_id, project_id, (body.title or "New chat").strip(), now, now),
    )
    conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id))
    conn.commit()
    return dict(conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone())


@router.get("/chats")
def recent_chats(
    limit: int = 20, conn: sqlite3.Connection = Depends(db.get_db)
) -> list[dict]:
    limit = max(1, min(limit, 100))
    rows = conn.execute(
        "SELECT c.id, c.title, c.updated_at, c.project_id, p.name AS project_name,"
        " (SELECT COUNT(*) FROM messages m WHERE m.chat_id = c.id) AS message_count"
        " FROM chats c LEFT JOIN projects p ON p.id = c.project_id"
        " ORDER BY c.updated_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return db.to_dicts(rows)


@router.get("/chats/{chat_id}")
def get_chat(
    chat_id: str,
    limit: int = 100,
    before: int | None = None,
    conn: sqlite3.Connection = Depends(db.get_db),
) -> dict:
    chat = fetch_chat(conn, chat_id)
    limit = max(1, min(limit, 200))
    if before is None:
        rows = conn.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM messages WHERE chat_id = ? AND id < ? ORDER BY id DESC LIMIT ?",
            (chat_id, before, limit),
        ).fetchall()
    messages = [dict(row) for row in reversed(rows)]
    older = 0
    if messages:
        older = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE chat_id = ? AND id < ?",
            (chat_id, messages[0]["id"]),
        ).fetchone()[0]
    calls = db.to_dicts(
        conn.execute(
            "SELECT * FROM tool_calls WHERE chat_id = ? ORDER BY id DESC LIMIT 200",
            (chat_id,),
        ).fetchall()
    )
    return {"chat": dict(chat), "messages": messages, "calls": calls, "has_more": older > 0}


@router.patch("/chats/{chat_id}")
def rename_chat(
    chat_id: str, body: ChatPatch, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict:
    fetch_chat(conn, chat_id)
    conn.execute(
        "UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
        (body.title.strip(), db.now_iso(), chat_id),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone())


@router.delete("/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: str, conn: sqlite3.Connection = Depends(db.get_db)):
    fetch_chat(conn, chat_id)
    conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    return None


@router.post("/chat/{chat_id}", status_code=201)
def post_message(
    chat_id: str, body: MessageIn, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict:
    """One turn. No provider configured is a supported outcome, not an error."""
    fetch_chat(conn, chat_id)
    return runner.run_chat(conn, chat_id, body.content)
