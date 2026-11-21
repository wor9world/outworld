"""T3 — one chat turn with no provider; the run row is the source of truth."""

from __future__ import annotations

from app import db


def seed(client) -> str:
    project = client.post("/api/projects", json={"name": "P"}).json()
    return client.post(f"/api/projects/{project['id']}/chats", json={}).json()["id"]


def test_turn_without_provider(client) -> None:
    chat_id = seed(client)
    r = client.post(f"/api/chat/{chat_id}", json={"content": "hello world"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["warnings"] == ["llm_disabled"]
    assert body["assistant_message"] is None
    assert body["user_message"]["role"] == "user"
    assert isinstance(body["user_message"]["id"], int)


def test_message_is_persisted_and_titles_the_chat(client) -> None:
    chat_id = seed(client)
    client.post(f"/api/chat/{chat_id}", json={"content": "first message here"})
    body = client.get(f"/api/chats/{chat_id}").json()
    assert len(body["messages"]) == 1
    assert body["messages"][0]["content"] == "first message here"
    assert body["chat"]["title"] == "first message here"


def test_title_truncates_to_48(client) -> None:
    chat_id = seed(client)
    long = "x" * 120
    client.post(f"/api/chat/{chat_id}", json={"content": long})
    body = client.get(f"/api/chats/{chat_id}").json()
    assert body["chat"]["title"] == "x" * 48


def test_run_row_is_written(client) -> None:
    chat_id = seed(client)
    run_id = client.post(f"/api/chat/{chat_id}", json={"content": "abc"}).json()["run_id"]
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    finally:
        conn.close()
    assert row["intent"] == "abc"
    assert row["intent_source"] == "none"
    assert row["status"] == "ok"
    assert row["ended_at"] is not None


def test_empty_content_is_rejected(client) -> None:
    chat_id = seed(client)
    assert client.post(f"/api/chat/{chat_id}", json={"content": ""}).status_code == 422


def test_unknown_chat_is_404(client) -> None:
    assert client.post("/api/chat/" + "b" * 32, json={"content": "x"}).status_code == 404
