"""T2 — chats CRUD and listing."""

from __future__ import annotations

from app import db


def seed(client) -> tuple[dict, dict]:
    project = client.post("/api/projects", json={"name": "P"}).json()
    chat = client.post(f"/api/projects/{project['id']}/chats", json={"title": "hello"}).json()
    return project, chat


def test_create_and_list_chats(client) -> None:
    project, chat = seed(client)
    assert chat["title"] == "hello"
    listed = client.get(f"/api/projects/{project['id']}/chats").json()
    assert [c["id"] for c in listed] == [chat["id"]]
    assert listed[0]["message_count"] == 0


def test_recent_chats_across_projects(client) -> None:
    seed(client)
    recent = client.get("/api/chats?limit=5").json()
    assert len(recent) == 1
    assert recent[0]["project_name"] == "P"


def test_get_chat_payload(client) -> None:
    _, chat = seed(client)
    body = client.get(f"/api/chats/{chat['id']}").json()
    assert body["chat"]["id"] == chat["id"]
    assert body["messages"] == []
    assert body["calls"] == []
    assert body["has_more"] is False


def test_rename_chat(client) -> None:
    _, chat = seed(client)
    r = client.patch(f"/api/chats/{chat['id']}", json={"title": "renamed"})
    assert r.status_code == 200
    assert r.json()["title"] == "renamed"


def test_delete_chat_removes_messages(client) -> None:
    _, chat = seed(client)
    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO messages (chat_id, role, content, created_at)"
            " VALUES (?, 'user', 'hi', ?)",
            (chat["id"], db.now_iso()),
        )
        conn.commit()
    finally:
        conn.close()
    assert client.delete(f"/api/chats/{chat['id']}").status_code == 204
    conn = db.connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
    finally:
        conn.close()


def test_unknown_chat_is_404(client) -> None:
    assert client.get("/api/chats/" + "a" * 32).status_code == 404
    assert client.get("/api/chats/../etc").status_code == 404
