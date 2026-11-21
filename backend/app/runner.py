"""One chat turn: open a run, store the user message, run the pipe or the agent, close.

This module is shared by the synchronous endpoint and the SSE endpoint so the two paths
cannot drift apart.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from . import db

MAX_INTENT = 200
TITLE_CHARS = 48


def normalize_intent(message: str) -> str:
    return " ".join(message.split())[:MAX_INTENT]


def llm_enabled(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM providers WHERE enabled = 1 AND model <> ''"
    ).fetchone()
    return bool(row[0])


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
    import json

    now = db.now_iso()
    meta_json = json.dumps(meta, ensure_ascii=False)
    cursor = conn.execute(
        "INSERT INTO messages (chat_id, role, content, meta_json, created_at)"
        " VALUES (?, 'assistant', ?, ?, ?)",
        (chat_id, content, meta_json, now),
    )
    conn.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (now, chat_id))
    return {
        "id": cursor.lastrowid,
        "chat_id": chat_id,
        "role": "assistant",
        "content": content,
        "meta_json": meta_json,
        "created_at": now,
    }


def run_chat(conn: sqlite3.Connection, chat_id: str, content: str) -> dict[str, Any]:
    """Synchronous turn. With no provider it stores the message and reports why."""
    chat = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
    project_id = chat["project_id"] if chat is not None else None
    run_id = open_run(conn, chat_id, project_id, content)
    user_message = add_user_message(conn, chat_id, content)

    if not llm_enabled(conn):
        close_run(conn, run_id, "ok")
        conn.commit()
        return {
            "run_id": run_id,
            "user_message": user_message,
            "assistant_message": None,
            "warnings": ["llm_disabled"],
        }

    # The agent path lands in T15; until then a configured provider still behaves
    # deterministically instead of pretending to answer.
    close_run(conn, run_id, "error")
    conn.commit()
    return {
        "run_id": run_id,
        "user_message": user_message,
        "assistant_message": None,
        "warnings": ["agent_not_wired"],
    }
