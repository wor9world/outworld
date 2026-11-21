"""T2 — projects CRUD, validation, cascade."""

from __future__ import annotations

from app import db


def make_project(client, name: str = "Alpha", root_path: str = ".") -> dict:
    r = client.post("/api/projects", json={"name": name, "root_path": root_path})
    assert r.status_code == 201, r.text
    return r.json()


def test_create_and_list(client) -> None:
    created = make_project(client, "Alpha")
    assert created["name"] == "Alpha"
    assert created["root_path"] == "."
    assert len(created["id"]) == 32

    listed = client.get("/api/projects").json()
    assert [p["name"] for p in listed] == ["Alpha"]
    assert listed[0]["chat_count"] == 0


def test_get_project_aggregate(client) -> None:
    project = make_project(client, "Beta")
    client.post(f"/api/projects/{project['id']}/chats", json={})
    body = client.get(f"/api/projects/{project['id']}").json()
    assert body["project"]["id"] == project["id"]
    assert len(body["chats"]) == 1
    assert body["notes"] == []
    assert body["commands"] == []


def test_patch_project(client) -> None:
    project = make_project(client, "Gamma")
    r = client.patch(f"/api/projects/{project['id']}", json={"name": "Gamma 2"})
    assert r.status_code == 200
    assert r.json()["name"] == "Gamma 2"


def test_root_path_guards(client) -> None:
    bad = client.post("/api/projects", json={"name": "x", "root_path": "../outside"})
    assert bad.status_code == 400
    assert bad.json()["message"]
    absolute = client.post("/api/projects", json={"name": "x", "root_path": "C:/Windows"})
    assert absolute.status_code == 400


def test_delete_cascades_chats(client) -> None:
    project = make_project(client, "Delta")
    chat = client.post(f"/api/projects/{project['id']}/chats", json={}).json()
    assert client.delete(f"/api/projects/{project['id']}").status_code == 204
    conn = db.connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM chats WHERE id = ?", (chat["id"],)).fetchone()[0] == 0
    finally:
        conn.close()


def test_unknown_project_is_404(client) -> None:
    r = client.get("/api/projects/0123456789abcdef0123456789abcdef")
    assert r.status_code == 404
    assert r.json()["message"] == "project not found"
