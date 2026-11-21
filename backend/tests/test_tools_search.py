"""T8 — search across knowledge, workspace, and the unconfigured web seam."""

from __future__ import annotations


def search(client, **args):
    return client.post("/api/tools/search", json=args)


def test_knowledge_scope(client) -> None:
    client.post("/api/knowledge", json={"title": "n", "body": "sympy parse_expr helper"})
    r = search(client, scope="knowledge", q="parse_expr")
    assert r.json()["ok"] is True
    assert len(r.json()["data"]["hits"]) == 1


def test_workspace_scope(client, workspace) -> None:
    (workspace / "notes.md").write_text("the quick brown fox\n", encoding="utf-8")
    r = search(client, scope="workspace", q="brown")
    body = r.json()
    assert body["ok"] is True
    assert body["data"]["hits"][0]["path"] == "notes.md"
    assert "brown" in body["data"]["hits"][0]["snippet"]


def test_workspace_skips_node_modules(client, workspace) -> None:
    ignored = workspace / "node_modules" / "pkg"
    ignored.mkdir(parents=True)
    (ignored / "index.js").write_text("needle-here", encoding="utf-8")
    r = search(client, scope="workspace", q="needle-here")
    assert r.json()["data"]["hits"] == []


def test_workspace_thai(client, workspace) -> None:
    (workspace / "th.md").write_text("สวัสดีชาวโลก", encoding="utf-8")
    r = search(client, scope="workspace", q="ชาวโลก")
    assert len(r.json()["data"]["hits"]) == 1


def test_web_without_key_is_explicit(client) -> None:
    r = search(client, scope="web", q="ai news")
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["error"] == "web_search_not_configured"


def test_query_required(client) -> None:
    assert search(client, scope="workspace", q="  ").json()["error"] == "query_required"
