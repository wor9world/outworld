"""Script tools: manifest layout, parameters, execution, agent exposure."""

from __future__ import annotations

import json


def script(client, **args):
    return client.post("/api/tools/script", json=args)


def write(client, name: str = "hello", **extra):
    body = {
        "op": "write",
        "name": name,
        "source": "print('hi')",
        "description": "say hi",
        "language": "python",
        "params": [],
        **extra,
    }
    return script(client, **body)


def test_write_creates_source_and_manifest(client, workspace) -> None:
    body = write(client, "hello").json()
    assert body["ok"] is True
    assert (workspace / "scripts" / "hello.py").exists()
    manifest = json.loads((workspace / "scripts" / "hello.json").read_text(encoding="utf-8"))
    assert manifest["language"] == "python"
    assert manifest["description"] == "say hi"


def test_list_and_read(client) -> None:
    write(client, "hello")
    listed = script(client, op="list").json()["data"]["scripts"]
    assert [row["name"] for row in listed] == ["hello"]
    read = script(client, op="read", name="hello").json()
    assert read["data"]["source"].startswith("print")


def test_run_with_param(client) -> None:
    script(
        client,
        op="write",
        name="greet",
        language="python",
        source="import sys\nprint('hi ' + sys.argv[1])",
        params=["who"],
        description="greet someone",
    )
    ok = script(client, op="run", name="greet", params_values={"who": "bob"}).json()
    assert ok["ok"] is True
    assert ok["data"]["stdout"].strip() == "hi bob"


def test_run_missing_param(client) -> None:
    script(
        client,
        op="write",
        name="greet",
        source="print('x')",
        params=["who"],
    )
    body = script(client, op="run", name="greet").json()
    assert body["ok"] is False
    assert body["error"] == "missing_param:who"


def test_unknown_script(client) -> None:
    assert script(client, op="run", name="ghost").json()["error"] == "not_found"


def test_bad_name_is_rejected(client) -> None:
    body = write(client, "../escape").json()
    assert body["ok"] is False
    assert body["error"] == "invalid_script_name"


def test_bad_param_name(client) -> None:
    body = script(client, op="write", name="p", source="print(1)", params=["bad name"]).json()
    assert body["error"].startswith("invalid_param:")


def test_delete_removes_both_files(client, workspace) -> None:
    write(client, "temp")
    assert script(client, op="delete", name="temp").json()["ok"] is True
    assert not (workspace / "scripts" / "temp.py").exists()
    assert not (workspace / "scripts" / "temp.json").exists()


def test_language_switch_removes_stale_extension(client, workspace) -> None:
    write(client, "swap", language="python")
    write(client, "swap", language="javascript", source="console.log(1)")
    assert (workspace / "scripts" / "swap.js").exists()
    assert not (workspace / "scripts" / "swap.py").exists()


def test_timeout_is_enforced(client) -> None:
    script(
        client,
        op="write",
        name="slow",
        source="import time\ntime.sleep(30)",
        timeout_s=1,
    )
    body = script(client, op="run", name="slow").json()
    assert body["ok"] is False
    assert body["error"] == "timeout"


def test_script_is_registered_as_a_tool(client) -> None:
    assert "script" in client.get("/api/health").json()["tools"]


def test_agent_catalogue_exposes_scripts(client) -> None:
    from app import agent

    write(client, "hello", description="say hi")
    names = {entry["function"]["name"] for entry in agent.tool_catalogue()}
    assert "script__hello" in names
    assert "script" in names
