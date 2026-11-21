"""T15 — the no-LLM paths: pipe answers, unmatched messages are explicit."""

from __future__ import annotations

from app import db


def seed(client) -> str:
    project = client.post("/api/projects", json={"name": "P"}).json()
    return client.post(f"/api/projects/{project['id']}/chats", json={}).json()["id"]


def test_pipe_answers_without_provider(client) -> None:
    chat_id = seed(client)
    body = client.post(f"/api/chat/{chat_id}", json={"content": "9.8-9.11=?"}).json()
    assert body["assistant_message"]["content"] == "0.69"
    assert body["warnings"] == []
    assert body["intent"] == "math_calc"


def test_unmatched_without_provider_is_explicit(client) -> None:
    chat_id = seed(client)
    body = client.post(f"/api/chat/{chat_id}", json={"content": "สวัสดี"}).json()
    assert body["assistant_message"] is None
    assert body["warnings"] == ["no_route"]


def test_runs_record_the_pipe_source(client) -> None:
    chat_id = seed(client)
    run_id = client.post(f"/api/chat/{chat_id}", json={"content": "3^x=x^9"}).json()["run_id"]
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    finally:
        conn.close()
    assert row["intent_source"] == "pipe"
    assert row["matched_rule"] == "math_solve"
    assert row["status"] == "ok"


def test_pipe_tool_calls_are_linked(client) -> None:
    chat_id = seed(client)
    body = client.post(f"/api/chat/{chat_id}", json={"content": "9.8-9.11=?"}).json()
    meta = body["assistant_message"]["meta_json"]
    assert "tool_call_ids" in meta
    assert body["intent"] == "math_calc"
