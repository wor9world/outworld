"""T16b — project command snippets: CRUD, templating, execution through shell."""

from __future__ import annotations


def seed(client) -> str:
    return client.post("/api/projects", json={"name": "P"}).json()["id"]


def make_command(client, **overrides) -> dict:
    project_id = overrides.pop("project_id", None) or seed(client)
    body = {"name": "status", "template": "git status", "params": [], **overrides}
    r = client.post(f"/api/projects/{project_id}/commands", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_and_list(client) -> None:
    command = make_command(client)
    assert command["name"] == "status"
    listed = client.get(f"/api/projects/{command['project_id']}/commands").json()
    assert [row["id"] for row in listed] == [command["id"]]


def test_patch_and_delete(client) -> None:
    command = make_command(client)
    patched = client.patch(
        f"/api/commands/{command['id']}", json={"template": "git log", "params": []}
    ).json()
    assert patched["template"] == "git log"
    assert client.delete(f"/api/commands/{command['id']}").status_code == 204
    assert client.get(f"/api/projects/{command['project_id']}/commands").json() == []


def test_run_allowlisted_command(client) -> None:
    command = make_command(client, template="echo hello-world")
    r = client.post(f"/api/commands/{command['id']}/run", json={"params": {}})
    assert r.status_code == 200
    assert r.json()["data"]["stdout"].strip() == "hello-world"


def test_render_params(client) -> None:
    command = make_command(client, template="echo {{word}}", params=["word"])
    r = client.post(f"/api/commands/{command['id']}/run", json={"params": {"word": "ok"}})
    assert r.json()["data"]["stdout"].strip() == "ok"


def test_missing_param_is_400(client) -> None:
    command = make_command(client, template="echo {{word}}", params=["word"])
    r = client.post(f"/api/commands/{command['id']}/run", json={"params": {}})
    assert r.status_code == 400
    assert r.json()["message"] == "missing_param:word"


def test_not_allowlisted_needs_approval(client) -> None:
    command = make_command(client, template="hostname")
    r = client.post(f"/api/commands/{command['id']}/run", json={"params": {}})
    assert r.status_code == 409
    assert r.json()["approval_token"].startswith("ap-")


def test_run_is_audited(client) -> None:
    command = make_command(client, template="echo audited")
    client.post(f"/api/commands/{command['id']}/run", json={"params": {}})
    calls = client.get("/api/calls").json()
    assert any(row["tool"] == "shell" for row in calls)
