"""T13 — pipe routing matrix (SPEC §14.6) and plan execution."""

from __future__ import annotations

import pytest


def route(client, message: str) -> dict:
    r = client.post("/api/pipe/route", json={"message": message})
    assert r.status_code == 200, r.text
    return r.json()


def run_pipe(client, message: str) -> dict:
    r = client.post("/api/pipe/run", json={"message": message})
    assert r.status_code == 200, r.text
    return r.json()


CASES = [
    ("9.8-9.11=?", "math_calc", "calc"),
    ("3^x=x^9", "math_solve", "calc"),
    ("วางแผน ทำระบบล็อกอิน", "plan", "planner"),
    ("สร้างโปรเจค hello", "project_create", "project"),
    ("ตรวจโปรเจค hello", "project_verify", "project"),
    ("ข่าวเอไอล่าสุด", "news", "search"),
    ("ค้นหา sympy docs", "search", "search"),
]


@pytest.mark.parametrize(("message", "intent", "tool"), CASES)
def test_route_matrix(client, message: str, intent: str, tool: str) -> None:
    body = route(client, message)
    assert body["intent"] == intent, body
    assert body["confidence"] >= 0.6
    assert body["steps"][0]["tool"] == tool


def test_route_never_executes(client) -> None:
    before = client.get("/api/calls").json()
    route(client, "9.8-9.11=?")
    after = client.get("/api/calls").json()
    assert len(before) == len(after)


def test_calc_answer_is_exact(client) -> None:
    body = run_pipe(client, "9.8-9.11=?")
    assert body["intent"] == "math_calc"
    assert body["answer"] == "0.69"
    assert body["results"][0]["result"]["data"]["exact"] == "69/100"


def test_solve_answer_has_both_roots(client) -> None:
    body = run_pipe(client, "3^x=x^9")
    assert body["intent"] == "math_solve"
    assert "27" in body["answer"]
    assert "1.1508248213" in body["answer"]


def test_plan_answer_lists_steps(client) -> None:
    body = run_pipe(client, "วางแผน ทำระบบล็อกอิน")
    assert body["intent"] == "plan"
    assert len(body["results"][0]["result"]["data"]["steps"]) >= 3
    assert ";" in body["answer"]


def test_project_create_and_verify(client, workspace) -> None:
    body = run_pipe(client, "สร้างโปรเจค hello")
    assert body["intent"] == "project_create"
    assert (workspace / "hello" / "pyproject.toml").exists()
    assert "created hello" in body["answer"]
    assert "ok" in body["answer"]

    again = run_pipe(client, "ตรวจโปรเจค hello")
    assert again["intent"] == "project_verify"
    assert "ok" in again["answer"]


def test_news_without_key_is_explicit(client) -> None:
    body = run_pipe(client, "ข่าวเอไอล่าสุด")
    assert body["intent"] == "news"
    assert body["error"].startswith("step_failed:web_search_not_configured")


def test_unmatched_message(client) -> None:
    body = run_pipe(client, "สวัสดี")
    assert body["intent"] is None
    assert body["error"] == "no_route"


def test_rules_endpoint(client) -> None:
    body = client.get("/api/pipe/rules").json()
    assert body["counts"]["intents"] == 7
    assert body["counts"]["plans"] == 7
    assert {row["intent"] for row in body["plans"]} == {
        "math_calc", "math_solve", "plan", "project_create",
        "project_verify", "news", "search",
    }


def test_reload(client) -> None:
    body = client.post("/api/pipe/reload").json()
    assert body == {"intents": 7, "plans": 7}


def test_dispatch_is_audited(client) -> None:
    run_pipe(client, "9.8-9.11=?")
    calls = client.get("/api/calls").json()
    assert any(row["tool"] == "calc" for row in calls)
