"""SQLite access: schema, connection helpers, FTS triggers."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from . import config

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL DEFAULT '.',
    instructions TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'New chat',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS chats_project ON chats(project_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user','assistant','tool','system')),
    content TEXT NOT NULL,
    meta_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_chat ON messages(chat_id, id);

CREATE TABLE IF NOT EXISTS knowledge (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS knowledge_project ON knowledge(project_id);

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    title, body, tags,
    content='knowledge', content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge BEGIN
    INSERT INTO knowledge_fts(rowid, title, body, tags)
    VALUES (new.rowid, new.title, new.body, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS knowledge_ad AFTER DELETE ON knowledge BEGIN
    INSERT INTO knowledge_fts(knowledge_fts, rowid, title, body, tags)
    VALUES ('delete', old.rowid, old.title, old.body, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS knowledge_au AFTER UPDATE ON knowledge BEGIN
    INSERT INTO knowledge_fts(knowledge_fts, rowid, title, body, tags)
    VALUES ('delete', old.rowid, old.title, old.body, old.tags);
    INSERT INTO knowledge_fts(rowid, title, body, tags)
    VALUES (new.rowid, new.title, new.body, new.tags);
END;

CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('openai','ollama')),
    base_url TEXT NOT NULL,
    model TEXT NOT NULL,
    api_key TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0,1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS commands (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    template TEXT NOT NULL,
    params_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT,
    run_id TEXT,
    tool TEXT NOT NULL,
    args_json TEXT NOT NULL,
    result_json TEXT,
    status TEXT NOT NULL CHECK (status IN ('ok','error','denied','timeout')),
    error TEXT,
    ms INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS tool_calls_chat ON tool_calls(chat_id, id DESC);
CREATE INDEX IF NOT EXISTS tool_calls_run ON tool_calls(run_id, id);
CREATE INDEX IF NOT EXISTS tool_calls_time ON tool_calls(created_at DESC);

CREATE TABLE IF NOT EXISTS approvals (
    token TEXT PRIMARY KEY,
    tool TEXT NOT NULL,
    args_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','approved','denied','expired')),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS approvals_pending ON approvals(status, expires_at);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    chat_id TEXT REFERENCES chats(id) ON DELETE CASCADE,
    project_id TEXT,
    intent TEXT NOT NULL,
    intent_source TEXT NOT NULL CHECK (intent_source IN ('pipe','llm','none')),
    matched_rule TEXT,
    status TEXT NOT NULL CHECK (status IN ('running','ok','error','denied','aborted')),
    iterations INTEGER NOT NULL DEFAULT 0,
    tool_count INTEGER NOT NULL DEFAULT 0,
    tokens INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    ended_at TEXT
);
CREATE INDEX IF NOT EXISTS runs_chat ON runs(chat_id, started_at DESC);
CREATE INDEX IF NOT EXISTS runs_time ON runs(started_at DESC);

CREATE TABLE IF NOT EXISTS patterns (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    intent TEXT NOT NULL,
    tool_chain_json TEXT NOT NULL,
    args_template_json TEXT NOT NULL,
    uses INTEGER NOT NULL DEFAULT 0,
    success INTEGER NOT NULL DEFAULT 0,
    last_used_at TEXT,
    source_run_id TEXT,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
    created_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS pattern_fts USING fts5(
    name, intent,
    content='patterns', content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS pattern_ai AFTER INSERT ON patterns BEGIN
    INSERT INTO pattern_fts(rowid, name, intent) VALUES (new.rowid, new.name, new.intent);
END;

CREATE TRIGGER IF NOT EXISTS pattern_ad AFTER DELETE ON patterns BEGIN
    INSERT INTO pattern_fts(pattern_fts, rowid, name, intent)
    VALUES ('delete', old.rowid, old.name, old.intent);
END;

CREATE TRIGGER IF NOT EXISTS pattern_au AFTER UPDATE ON patterns BEGIN
    INSERT INTO pattern_fts(pattern_fts, rowid, name, intent)
    VALUES ('delete', old.rowid, old.name, old.intent);
    INSERT INTO pattern_fts(rowid, name, intent) VALUES (new.rowid, new.name, new.intent);
END;

CREATE TABLE IF NOT EXISTS feedback (
    run_id TEXT PRIMARY KEY REFERENCES runs(id) ON DELETE CASCADE,
    verdict TEXT NOT NULL CHECK (verdict IN ('good','bad')),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    path = config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def new_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + (
        f"{datetime.now(UTC).microsecond // 1000:03d}Z"
    )


def to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]
