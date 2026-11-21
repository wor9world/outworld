"""T7 — code tool: python, javascript, timeout, unsupported."""

from __future__ import annotations

import shutil
import time


def code(client, **args):
    return client.post("/api/tools/code", json=args)


def test_python_snippet(client) -> None:
    r = code(client, language="python", source="print(6*7)")
    assert r.json()["ok"] is True
    assert r.json()["data"]["stdout"].strip() == "42"


def test_python_error_exit_code(client) -> None:
    r = code(client, language="python", source="raise SystemExit(3)")
    assert r.json()["ok"] is False
    assert r.json()["data"]["exit_code"] == 3


def test_javascript_runs_when_bun_present(client) -> None:
    r = code(client, language="javascript", source="console.log(6*7)")
    body = r.json()
    if shutil.which("bun") is None:
        assert body["error"] == "unsupported_language"
    else:
        assert body["ok"] is True
        assert body["data"]["stdout"].strip() == "42"


def test_timeout_kills_the_snippet(client) -> None:
    started = time.perf_counter()
    r = code(client, language="python", source="while True: pass", timeout_s=1)
    elapsed = time.perf_counter() - started
    assert r.json()["ok"] is False
    assert r.json()["error"] == "timeout"
    assert elapsed < 15


def test_unsupported_language(client) -> None:
    r = code(client, language="ruby", source="puts 1")
    assert r.json()["error"] == "unsupported_language"


def test_empty_source(client) -> None:
    assert code(client, language="python", source="  ").json()["error"] == "source_required"


def test_temp_dir_is_cleaned(client, workspace) -> None:
    code(client, language="python", source="print(1)")
    leftovers = [p for p in (workspace / ".tmp").glob("run-*")]
    assert leftovers == []
