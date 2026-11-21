"""T3 — message paging with before/limit and has_more."""

from __future__ import annotations

from app import db


def seed(client, count: int) -> str:
    project = client.post("/api/projects", json={"name": "P"}).json()
    chat_id = client.post(f"/api/projects/{project['id']}/chats", json={}).json()["id"]
    conn = db.connect()
    try:
        for i in range(count):
            conn.execute(
                "INSERT INTO messages (chat_id, role, content, created_at)"
                " VALUES (?, 'user', ?, ?)",
                (chat_id, f"m{i}", db.now_iso()),
            )
        conn.commit()
    finally:
        conn.close()
    return chat_id


def test_default_returns_all_and_no_more(client) -> None:
    chat_id = seed(client, 5)
    body = client.get(f"/api/chats/{chat_id}").json()
    assert [m["content"] for m in body["messages"]] == ["m0", "m1", "m2", "m3", "m4"]
    assert body["has_more"] is False


def test_limit_returns_newest_slice_ascending(client) -> None:
    chat_id = seed(client, 5)
    body = client.get(f"/api/chats/{chat_id}?limit=2").json()
    assert [m["content"] for m in body["messages"]] == ["m3", "m4"]
    assert body["has_more"] is True


def test_before_walks_backwards(client) -> None:
    chat_id = seed(client, 5)
    first = client.get(f"/api/chats/{chat_id}?limit=2").json()["messages"][0]["id"]
    body = client.get(f"/api/chats/{chat_id}?limit=2&before={first}").json()
    assert [m["content"] for m in body["messages"]] == ["m1", "m2"]
    assert body["has_more"] is True

    oldest = body["messages"][0]["id"]
    body = client.get(f"/api/chats/{chat_id}?limit=2&before={oldest}").json()
    assert [m["content"] for m in body["messages"]] == ["m0"]
    assert body["has_more"] is False


def test_limit_is_capped(client) -> None:
    chat_id = seed(client, 3)
    body = client.get(f"/api/chats/{chat_id}?limit=100000").json()
    assert len(body["messages"]) == 3
