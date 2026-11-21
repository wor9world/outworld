"""T6 — shell allowlist, approval mint/approve/deny, timeout, audit."""

from __future__ import annotations


def shell(client, **args):
    return client.post("/api/tools/shell", json=args)


def test_allowlisted_command_runs(client) -> None:
    r = shell(client, command="echo hi")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["data"]["stdout"].strip() == "hi"
    assert r.json()["data"]["exit_code"] == 0


def test_not_allowlisted_needs_approval(client) -> None:
    r = shell(client, command="rm -rf workspace")
    assert r.status_code == 409
    body = r.json()
    assert body["error"] == "approval_required"
    assert body["approval_token"].startswith("ap-")
    assert body["message"] == "approval_required"


def test_chain_always_needs_approval(client) -> None:
    for command in ("echo a && echo b", "echo a | echo b", "echo a; echo b", "echo $(whoami)"):
        r = shell(client, command=command)
        assert r.status_code == 409, command


def test_approve_executes_once(client) -> None:
    token = shell(client, command="hostname").json()["approval_token"]
    first = client.post(f"/api/approvals/{token}", json={"decision": "approve"})
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "approved"
    assert body["result"]["ok"] is True
    assert body["result"]["data"]["stdout"].strip() != ""

    again = client.post(f"/api/approvals/{token}", json={"decision": "approve"})
    assert again.status_code == 410
    assert again.json()["message"] == "approval_approved"


def test_deny_does_not_run(client) -> None:
    token = shell(client, command="del /s /q C:\\").json()["approval_token"]
    r = client.post(f"/api/approvals/{token}", json={"decision": "deny"})
    assert r.status_code == 200
    assert r.json()["status"] == "denied"
    assert r.json()["result"]["error"] == "denied"


def test_timeout_is_reported(client) -> None:
    r = client.post(
        "/api/tools/shell",
        json={"command": "ping -n 10 127.0.0.1", "timeout_s": 1, "approved": True},
    )
    assert r.json()["ok"] is False
    assert r.json()["error"] == "timeout"


def test_denied_call_is_audited(client) -> None:
    token = shell(client, command="format c:").json()["approval_token"]
    client.post(f"/api/approvals/{token}", json={"decision": "deny"})
    calls = client.get("/api/calls").json()
    assert any(row["status"] == "denied" for row in calls)


def test_cwd_is_sandboxed(client) -> None:
    r = shell(client, command="echo hi", cwd="../../")
    assert r.status_code == 403
    assert r.json()["error"] == "outside_workspace"
