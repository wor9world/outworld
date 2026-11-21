"""T16 — pattern CRUD and the memory tool."""

from __future__ import annotations


def seed(client) -> tuple[str, str]:
    project = client.post("/api/projects", json={"name": "P"}).json()
    chat = client.post(f"/api/projects/{project['id']}/chats", json={}).json()
    return project["id"], chat["id"]


def make_pattern(client) -> dict:
    _, chat_id = seed(client)
    client.post(f"/api/chat/{chat_id}", json={"content": "สร้างโปรเจค pat"})
    return client.get("/api/patterns").json()[0]


def test_pattern_detail_includes_sample_run(client) -> None:
    row = make_pattern(client)
    body = client.get(f"/api/patterns/{row['id']}").json()
    assert body["pattern"]["intent"] == "สร้างโปรเจค pat"
    assert body["pattern"]["tool_chain_json"] == '["project", "project"]'
    assert body["sample_run"]["intent_source"] == "pipe"


def test_pattern_search_by_query(client) -> None:
    make_pattern(client)
    hits = client.get("/api/patterns?q=สร้างโปรเจค").json()
    assert len(hits) == 1


def test_pattern_rename_and_delete(client) -> None:
    row = make_pattern(client)
    renamed = client.patch(f"/api/patterns/{row['id']}", json={"name": "scaffold flow"}).json()
    assert renamed["name"] == "scaffold flow"
    assert client.delete(f"/api/patterns/{row['id']}").status_code == 204
    assert client.get(f"/api/patterns/{row['id']}").status_code == 404


def test_memory_save_search_forget(client) -> None:
    saved = client.post(
        "/api/tools/memory",
        json={"op": "save", "name": "calc chain", "intent": "math pipeline",
              "tool_chain": ["calc", "knowledge"]},
    ).json()
    assert saved["ok"] is True
    assert saved["data"]["id"]

    found = client.post("/api/tools/memory", json={"op": "search", "q": "math pipeline"}).json()
    assert found["ok"] is True
    assert len(found["data"]["patterns"]) == 1

    forgotten = client.post("/api/tools/memory", json={"op": "forget", "name": "calc chain"}).json()
    assert forgotten["data"]["disabled"] == 1
    again = client.post("/api/tools/memory", json={"op": "search", "q": "math pipeline"}).json()
    assert again["data"]["patterns"] == []


def test_memory_rejects_incomplete_save(client) -> None:
    body = client.post("/api/tools/memory", json={"op": "save", "name": "x"}).json()
    assert body["ok"] is False
    assert body["error"] == "name_intent_chain_required"
