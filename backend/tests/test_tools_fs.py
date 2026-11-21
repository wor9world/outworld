"""T5 — fs tool, workspace sandbox, tool dispatch, audit."""

from __future__ import annotations

from app import db


def call(client, tool: str, **args):
    return client.post(f"/api/tools/{tool}", json=args)


def test_write_then_read(client) -> None:
    w = call(client, "fs", op="write", path="notes/a.md", content="hello")
    assert w.status_code == 200
    assert w.json()["ok"] is True
    assert w.json()["data"]["path"] == "notes/a.md"

    r = call(client, "fs", op="read", path="notes/a.md")
    assert r.json()["data"]["content"] == "hello"


def test_list(client) -> None:
    call(client, "fs", op="write", path="a.txt", content="1")
    call(client, "fs", op="write", path="b/c.txt", content="2")
    entries = call(client, "fs", op="list", path=".").json()["data"]["entries"]
    names = [e["name"] for e in entries]
    assert "a.txt" in names
    assert "b" in names
    assert all(e["name"] not in {"node_modules", ".git"} for e in entries)


def test_patch_single_match(client) -> None:
    call(client, "fs", op="write", path="p.txt", content="a b a")
    r = call(client, "fs", op="patch", path="p.txt", old="b", new="B")
    assert r.json()["ok"] is True
    assert call(client, "fs", op="read", path="p.txt").json()["data"]["content"] == "a B a"


def test_patch_ambiguous_is_409(client) -> None:
    call(client, "fs", op="write", path="p.txt", content="a a")
    r = call(client, "fs", op="patch", path="p.txt", old="a", new="b")
    assert r.status_code == 409
    assert r.json()["error"] == "ambiguous_patch"


def test_outside_workspace_is_403(client, workspace) -> None:
    for path in ("../../AGENTS.md", "C:/Windows/win.ini", "../.outworld/brief.md"):
        r = call(client, "fs", op="write", path=path, content="pwned")
        assert r.status_code == 403, path
        assert r.json()["error"] == "outside_workspace"
    assert not (workspace.parent / "AGENTS.md").exists()


def test_missing_file_is_404(client) -> None:
    r = call(client, "fs", op="read", path="nope.txt")
    assert r.status_code == 200
    assert r.json()["error"] == "not_found"


def test_unknown_tool_is_404(client) -> None:
    assert call(client, "nope").status_code == 404


def test_audit_row_written(client) -> None:
    call(client, "fs", op="write", path="x.txt", content="y", chat_id="c1", run_id="r1")
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT * FROM tool_calls WHERE tool = 'fs' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row["status"] == "ok"
    assert row["chat_id"] == "c1"
    assert row["run_id"] == "r1"
    assert row["ms"] >= 0


def test_tools_listing_has_fs(client) -> None:
    tools = client.get("/api/tools").json()
    assert "fs" in {t["id"] for t in tools}
