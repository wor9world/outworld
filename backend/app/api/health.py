"""GET /api/health — proves the process, the DB and the tool registry are alive."""

from __future__ import annotations

import platform

from fastapi import APIRouter

from tools import registry

from .. import config, db

router = APIRouter()

VERSION = "2.0.0"


@router.get("/health")
def health() -> dict[str, object]:
    conn = db.connect()
    try:
        schema = conn.execute("PRAGMA user_version").fetchone()[0]
        llm = conn.execute(
            "SELECT COUNT(*) FROM providers WHERE enabled = 1 AND model <> ''"
        ).fetchone()[0]
    finally:
        conn.close()

    return {
        "status": "ok",
        "python": platform.python_version(),
        "version": VERSION,
        "tools": sorted(registry.public_tools()),
        "llm": "enabled" if llm else "disabled",
        "db": str(config.db_path()),
        "schema": int(schema),
        "theme": config.load_settings().get("theme", "system"),
    }
