"""T16 — learning: distillation, recall, feedback, promote."""

from __future__ import annotations

from app import db


def seed(client) -> tuple[str, str]:
    project = client.post("/api/projects", json={"name": "P"}).json()
    chat = client.post(f"/api/projects/{project['id']}/chats", json={}).json()
    return project["id"], chat["id"]


def patterns(client) -> list[dict]:
    return client.get("/api/patterns").json()


def test_single_tool_run_makes_no_pattern(client) -> None:
    _, chat_id = seed(client)
    client.post(f"/api/chat/{chat_id}", json={"content": "9.8-9.11=?"})
    assert patterns(client) == []


def test_two_tool_run_makes_one_pattern(client) -> None:
    _, chat_id = seed(client)
    client.post(f"/api/chat/{chat_id}", json={"content": "สร้างโปรเจค hello"})
    rows = patterns(client)
    assert len(rows) == 1
    assert rows[0]["tool_chain"] == ["project", "project"]
    assert rows[0]["uses"] == 1
    assert rows[0]["success"] == 1


def test_repeating_a_run_updates_the_same_row(client) -> None:
    _, chat_id = seed(client)
    client.post(f"/api/chat/{chat_id}", json={"content": "สร้างโปรเจค first"})
    second = client.post(f"/api/chat/{chat_id}", json={"content": "สร้างโปรเจค first"}).json()
    # The second scaffold hits target_exists, so it is a failed run: recall counts a
    # use, but success does not move.
    assert second["assistant_message"] is not None
    rows = patterns(client)
    assert len(rows) == 1
    assert rows[0]["uses"] == 2
    assert rows[0]["success"] == 1


def test_runs_endpoint_lists_the_turn(client) -> None:
    _, chat_id = seed(client)
    run_id = client.post(f"/api/chat/{chat_id}", json={"content": "ตรวจโปรเจค nope"}).json()[
        "run_id"
    ]
    runs = client.get("/api/runs").json()
    assert runs[0]["id"] == run_id
    detail = client.get(f"/api/runs/{run_id}").json()
    assert detail["run"]["intent_source"] == "pipe"
    assert detail["calls"]


def test_feedback_lowers_success(client) -> None:
    _, chat_id = seed(client)
    run_id = client.post(f"/api/chat/{chat_id}", json={"content": "สร้างโปรเจค fb"}).json()[
        "run_id"
    ]
    assert patterns(client)[0]["success"] == 1
    body = client.post(f"/api/runs/{run_id}/feedback", json={"verdict": "bad"}).json()
    assert body["verdict"] == "bad"
    assert patterns(client)[0]["success"] == 0


def test_zero_success_patterns_are_never_recalled(client) -> None:
    from app import learning

    _, chat_id = seed(client)
    run_id = client.post(f"/api/chat/{chat_id}", json={"content": "สร้างโปรเจค zero"}).json()[
        "run_id"
    ]
    client.post(f"/api/runs/{run_id}/feedback", json={"verdict": "bad"})
    conn = db.connect()
    try:
        assert learning.recall(conn, "สร้างโปรเจค zero") == []
    finally:
        conn.close()


def test_disable_removes_from_recall(client) -> None:
    from app import learning

    _, chat_id = seed(client)
    client.post(f"/api/chat/{chat_id}", json={"content": "สร้างโปรเจค off"})
    row = patterns(client)[0]
    conn = db.connect()
    try:
        assert learning.recall(conn, "สร้างโปรเจค off")
    finally:
        conn.close()
    client.patch(f"/api/patterns/{row['id']}", json={"enabled": False})
    conn = db.connect()
    try:
        assert learning.recall(conn, "สร้างโปรเจค off") == []
    finally:
        conn.close()


def test_promote_appends_instructions(client) -> None:
    project_id, chat_id = seed(client)
    client.post(f"/api/chat/{chat_id}", json={"content": "สร้างโปรเจค promo"})
    row = patterns(client)[0]
    body = client.post(
        f"/api/patterns/{row['id']}/promote", json={"project_id": project_id}
    ).json()
    assert "project → project" in body["instructions"]
    project = client.get(f"/api/projects/{project_id}").json()["project"]
    assert "project → project" in project["instructions"]


def test_stats_shape(client) -> None:
    _, chat_id = seed(client)
    client.post(f"/api/chat/{chat_id}", json={"content": "9.8-9.11=?"})
    stats = client.get("/api/learning/stats").json()
    assert stats["runs_total"] == 1
    assert stats["pipe_rate"] == 1.0
    assert 0 <= stats["ok_rate"] <= 1


def test_hints_text_is_bounded(client) -> None:
    from app import learning

    _, chat_id = seed(client)
    client.post(f"/api/chat/{chat_id}", json={"content": "สร้างโปรเจค bounded"})
    conn = db.connect()
    try:
        found = learning.recall(conn, "สร้างโปรเจค bounded")
        text = learning.hints(found)
    finally:
        conn.close()
    assert text.startswith("Known patterns for similar requests:")
    assert len(text) <= 600
