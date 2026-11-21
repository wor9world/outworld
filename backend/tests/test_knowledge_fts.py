"""T4 — knowledge CRUD and FTS5 (trigram) search, including Thai text."""

from __future__ import annotations


def note(client, title: str, body: str = "", **extra) -> dict:
    r = client.post("/api/knowledge", json={"title": title, "body": body, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_create_and_get(client) -> None:
    created = note(client, "Sympy notes", "solve equations with symbols")
    fetched = client.get(f"/api/knowledge/{created['id']}").json()
    assert fetched["title"] == "Sympy notes"
    assert fetched["body"].startswith("solve")


def test_search_english_substring(client) -> None:
    note(client, "Sympy", "the parse_expr helper uses transformations")
    hits = client.get("/api/knowledge?q=parse_expr").json()
    assert len(hits) == 1
    assert hits[0]["title"] == "Sympy"


def test_search_thai_substring(client) -> None:
    note(client, "บันทึก", "สวัสดีชาวโลก ยินดีต้อนรับ")
    hits = client.get("/api/knowledge?q=ชาวโลก").json()
    assert len(hits) == 1
    assert hits[0]["title"] == "บันทึก"


def test_search_prefix_english(client) -> None:
    note(client, "docs", "sympy documentation link")
    hits = client.get("/api/knowledge?q=symp").json()
    assert len(hits) == 1


def test_snippet_has_mark(client) -> None:
    note(client, "n", "the quick brown fox jumps")
    hits = client.get("/api/knowledge?q=brown&snippets=1").json()
    assert "<mark>" in hits[0]["snippet"]


def test_edit_updates_index(client) -> None:
    created = note(client, "n", "alpha beta gamma")
    assert len(client.get("/api/knowledge?q=alpha").json()) == 1
    client.patch(f"/api/knowledge/{created['id']}", json={"body": "delta epsilon"})
    assert client.get("/api/knowledge?q=alpha").json() == []
    assert len(client.get("/api/knowledge?q=delta").json()) == 1


def test_two_char_query_falls_back_to_like(client) -> None:
    note(client, "n", "ab cd")
    assert len(client.get("/api/knowledge?q=ab").json()) == 1


def test_project_filter(client) -> None:
    project = client.post("/api/projects", json={"name": "P"}).json()
    note(client, "inside", "x", project_id=project["id"])
    note(client, "outside", "x")
    hits = client.get(f"/api/knowledge?project_id={project['id']}").json()
    assert [h["title"] for h in hits] == ["inside"]


def test_delete_note(client) -> None:
    created = note(client, "temp", "body")
    assert client.delete(f"/api/knowledge/{created['id']}").status_code == 204
    assert client.get(f"/api/knowledge/{created['id']}").status_code == 404


def test_knowledge_tool_registered(client) -> None:
    assert "knowledge" in client.get("/api/health").json()["tools"]
