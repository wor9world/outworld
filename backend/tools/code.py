"""`code` tool: run a snippet in a throwaway directory under the workspace."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from app import config, sandbox

from .registry import register_tool


def _cap(text: str, limit: int) -> tuple[str, bool]:
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= limit:
        return text, False
    return raw[:limit].decode("utf-8", errors="ignore"), True


def _bun() -> str | None:
    return shutil.which("bun")


@register_tool(name="code", description="Run a Python or JavaScript snippet with a timeout")
def run(language: str, source: str, timeout_s: int | None = None) -> dict[str, Any]:
    if not isinstance(source, str) or not source.strip():
        return {"ok": False, "data": None, "meta": {}, "error": "source_required"}

    if language == "python":
        argv = [sys.executable, "-I", "-c", source]
    elif language == "javascript":
        bun = _bun()
        if bun is None:
            return {"ok": False, "data": None, "meta": {}, "error": "unsupported_language"}
        argv = [bun, "-e", source]
    else:
        return {"ok": False, "data": None, "meta": {}, "error": "unsupported_language"}

    settings = config.load_settings()
    timeout = int(timeout_s or settings.get("code_timeout_s", 20))
    limit = int(settings.get("max_output_bytes", 65536))
    base = sandbox.workspace() / ".tmp"
    base.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="run-", dir=base))

    started = time.perf_counter()
    try:
        completed = subprocess.run(  # noqa: S603 - argv is built from fixed interpreters
            argv,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "data": {"stdout": "", "stderr": f"timeout after {timeout}s", "exit_code": -1},
            "meta": {"ms": int((time.perf_counter() - started) * 1000)},
            "error": "timeout",
        }
    except OSError as exc:
        return {"ok": False, "data": None, "meta": {}, "error": f"os_error:{exc.strerror}"}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    stdout, out_cut = _cap(completed.stdout, limit)
    stderr, err_cut = _cap(completed.stderr, limit)
    return {
        "ok": completed.returncode == 0,
        "data": {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": completed.returncode,
            "truncated": out_cut or err_cut,
        },
        "meta": {"ms": int((time.perf_counter() - started) * 1000), "language": language},
        "error": None if completed.returncode == 0 else f"exit_{completed.returncode}",
    }
