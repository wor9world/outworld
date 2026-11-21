"""T14 + T15 — providers CRUD, SSE contract, stream parsers, agent loop."""

from __future__ import annotations

import json

from app import llm


def add_provider(client, **overrides):
    body = {
        "name": "local",
        "kind": "openai",
        "base_url": "http://127.0.0.1:9/v1",
        "model": "test-model",
        "api_key": "sk-secret",
        "enabled": True,
        **overrides,
    }
    r = client.post("/api/providers", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def seed_chat(client) -> str:
    project = client.post("/api/projects", json={"name": "P"}).json()
    return client.post(f"/api/projects/{project['id']}/chats", json={}).json()["id"]


def sse_events(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        name, data = "", ""
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = line[6:]
        if name:
            events.append((name, json.loads(data)))
    return events


# --- providers -------------------------------------------------------------


def test_provider_key_is_write_only(client) -> None:
    created = add_provider(client)
    assert "api_key" not in created
    listed = client.get("/api/providers").json()
    assert "api_key" not in listed[0]


def test_health_flips_to_enabled(client) -> None:
    assert client.get("/api/health").json()["llm"] == "disabled"
    add_provider(client)
    assert client.get("/api/health").json()["llm"] == "enabled"


def test_empty_key_keeps_the_old_one(client) -> None:
    provider = add_provider(client)
    client.patch(f"/api/providers/{provider['id']}", json={"api_key": "", "model": "other"})
    from app import db

    conn = db.connect()
    try:
        row = conn.execute("SELECT api_key, model FROM providers WHERE id = ?",
                           (provider["id"],)).fetchone()
    finally:
        conn.close()
    assert row["api_key"] == "sk-secret"
    assert row["model"] == "other"


def test_provider_test_reports_failure_cleanly(client) -> None:
    provider = add_provider(client)
    body = client.post(f"/api/providers/{provider['id']}/test").json()
    assert body["ok"] is False
    assert body["error"]


def test_unknown_provider_is_404(client) -> None:
    assert client.delete("/api/providers/" + "a" * 32).status_code == 404


# --- stream parsers --------------------------------------------------------


def test_parse_openai_text() -> None:
    lines = [
        'data: {"choices":[{"delta":{"content":"Hel"}}]}',
        'data: {"choices":[{"delta":{"content":"lo"}}]}',
        "data: [DONE]",
    ]
    events = list(llm.parse_openai(lines))
    assert [payload for kind, payload in events if kind == "delta"] == ["Hel", "lo"]
    assert events[-1] == ("final", {"content": "Hello", "tool_calls": []})


def test_parse_openai_tool_calls() -> None:
    lines = [
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1",'
        '"function":{"name":"calc","arguments":"{\\"op\\":"}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
        '"function":{"arguments":"\\"eval\\",\\"expr\\":\\"1+1\\"}"}}]}}]}',
    ]
    final = list(llm.parse_openai(lines))[-1][1]
    assert final["tool_calls"][0]["name"] == "calc"
    assert json.loads(final["tool_calls"][0]["arguments"]) == {"op": "eval", "expr": "1+1"}


def test_parse_ollama() -> None:
    lines = [
        '{"message":{"content":"Hi"},"done":false}',
        '{"message":{"content":" there"},"done":false}',
        '{"done":true}',
    ]
    events = list(llm.parse_ollama(lines))
    assert events[-1] == ("final", {"content": "Hi there", "tool_calls": []})


# --- streaming endpoint ----------------------------------------------------


def test_stream_without_provider_and_no_route_is_409(client) -> None:
    chat_id = seed_chat(client)
    r = client.post(f"/api/chat/{chat_id}/stream", json={"content": "สวัสดี"})
    assert r.status_code == 409
    assert r.json()["message"] == "llm_disabled"


def test_stream_pipe_route_without_provider(client) -> None:
    chat_id = seed_chat(client)
    with client.stream("POST", f"/api/chat/{chat_id}/stream",
                       json={"content": "9.8-9.11=?"}) as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())
    events = sse_events(text)
    names = [name for name, _ in events]
    assert names[0] == "start"
    assert "route" in names
    assert "done" in names
    delta = next(data for name, data in events if name == "delta")
    assert delta["text"] == "0.69"
    route = next(data for name, data in events if name == "route")
    assert route["intent"] == "math_calc"
    assert route["source"] == "pipe"


def test_agent_loop_executes_one_tool(client, monkeypatch) -> None:
    add_provider(client)
    chat_id = seed_chat(client)

    calls = {"n": 0}

    def fake_stream(provider, messages, tools=None):
        calls["n"] += 1
        if calls["n"] == 1:
            yield "final", {
                "content": "",
                "tool_calls": [{"id": "c1", "name": "calc",
                                "arguments": json.dumps({"op": "eval", "expr": "2+2"})}],
            }
        else:
            yield "delta", "the answer is 4"
            yield "final", {"content": "the answer is 4", "tool_calls": []}

    monkeypatch.setattr(llm, "stream", fake_stream)

    with client.stream("POST", f"/api/chat/{chat_id}/stream",
                       json={"content": "please compute 2+2 with a tool"}) as response:
        text = "".join(response.iter_text())

    events = sse_events(text)
    names = [name for name, _ in events]
    assert names[0] == "start"
    assert "route" in names
    assert "tool" in names
    assert "tool_result" in names
    assert names[-1] == "done"

    tool_event = next(data for name, data in events if name == "tool")
    assert tool_event["tool"] == "calc"
    assert any(data.get("text") == "the answer is 4" for name, data in events if name == "delta")
