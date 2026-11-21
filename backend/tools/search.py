"""`search` tool: knowledge notes, workspace files, and web when configured."""

from __future__ import annotations

from typing import Any

from app import config, db, sandbox

from . import knowledge as knowledge_store
from .registry import register_tool

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".svelte-kit", ".tmp", "build"}
MAX_FILE_BYTES = 1_048_576
CONTEXT = 80


def _workspace_hits(query: str, limit: int) -> list[dict[str, Any]]:
    needle = query.lower()
    root = sandbox.workspace()
    hits: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if len(hits) >= limit:
            break
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        index = text.lower().find(needle)
        if index < 0:
            continue
        start = max(0, index - CONTEXT)
        snippet = text[start : index + len(query) + CONTEXT].replace("\n", " ")
        hits.append(
            {
                "path": path.relative_to(root).as_posix(),
                "snippet": snippet,
                "rank": float(len(hits)),
            }
        )
    return hits


@register_tool(name="search", description="Search knowledge notes, workspace files or the web")
def run(scope: str = "knowledge", q: str = "", limit: int = 20, freshness: str | None = None) -> dict[str, Any]:
    query = (q or "").strip()
    if not query:
        return {"ok": False, "data": None, "meta": {}, "error": "query_required"}
    limit = max(1, min(int(limit), 100))

    if scope == "knowledge":
        conn = db.connect()
        try:
            hits = knowledge_store.search(conn, query, limit=limit, snippets=True)
        finally:
            conn.close()
        return {"ok": True, "data": {"hits": hits}, "meta": {"scope": scope}, "error": None}

    if scope == "workspace":
        hits = _workspace_hits(query, limit)
        return {"ok": True, "data": {"hits": hits}, "meta": {"scope": scope}, "error": None}

    if scope == "web":
        settings = config.load_settings()
        web = settings.get("web_search", {})
        if not web.get("enabled") or not web.get("api_key"):
            return {"ok": False, "data": None, "meta": {"scope": scope},
                    "error": "web_search_not_configured"}
        from app import websearch

        return websearch.search(query, limit=limit, freshness=freshness)

    return {"ok": False, "data": None, "meta": {}, "error": f"unknown_scope:{scope}"}
