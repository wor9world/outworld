"""T12 — project scaffold and verify."""

from __future__ import annotations


def project(client, **args):
    return client.post("/api/tools/project", json=args)


def test_scaffold_python(client, workspace) -> None:
    body = project(client, op="scaffold", name="hello", template="python").json()
    assert body["ok"] is True
    assert body["data"]["path"] == "hello"
    assert (workspace / "hello" / "pyproject.toml").exists()
    assert (workspace / "hello" / "tests" / "test_main.py").exists()


def test_scaffold_refuses_existing(client) -> None:
    project(client, op="scaffold", name="taken", template="static")
    again = project(client, op="scaffold", name="taken", template="static").json()
    assert again["ok"] is False
    assert again["error"] == "target_exists"


def test_verify_python_runs_pytest(client) -> None:
    project(client, op="scaffold", name="pyapp", template="python")
    body = project(client, op="verify", name="pyapp").json()
    assert body["ok"] is True, body
    names = [check["name"] for check in body["data"]["checks"]]
    assert "pytest" in names
    pytest_check = next(c for c in body["data"]["checks"] if c["name"] == "pytest")
    assert pytest_check["ok"] is True
    assert "passed" in pytest_check["output"]


def test_verify_static(client) -> None:
    project(client, op="scaffold", name="site", template="static")
    body = project(client, op="verify", name="site").json()
    assert body["ok"] is True
    assert body["data"]["checks"][0]["name"] == "index.html"


def test_unknown_template_and_bad_name(client) -> None:
    assert project(client, op="scaffold", name="x", template="cobol").json()["error"].startswith(
        "unknown_template"
    )
    assert project(client, op="scaffold", name="../escape").json()["error"] == "invalid_name"


def test_verify_missing_project(client) -> None:
    assert project(client, op="verify", name="ghost").json()["error"] == "not_found"
