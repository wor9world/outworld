"""`shell` tool.

Allowlisted commands run directly. Anything else returns ``approval_required`` and the
API layer mints a single-use token; approval re-runs the same args with ``approved=True``.
"""

from __future__ import annotations

import subprocess
import time
from typing import Any

from app import config, sandbox

from .registry import register_tool

CHAIN_MARKERS = ("&&", "||", ";", "|", ">", "<", "$(", "`", "&")


def is_allowlisted(command: str, allowlist: list[str]) -> bool:
    normalized = " ".join(command.strip().split()).lower()
    if not normalized:
        return False
    if any(marker in normalized for marker in CHAIN_MARKERS):
        return False
    return any(
        normalized == entry.lower() or normalized.startswith(entry.lower() + " ")
        for entry in allowlist
    )


def _cap(text: str, limit: int) -> tuple[str, bool]:
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= limit:
        return text, False
    return raw[:limit].decode("utf-8", errors="ignore"), True


@register_tool(name="shell", description="Run a shell command inside the workspace (allowlist or approval)")
def run(
    command: str,
    cwd: str = ".",
    timeout_s: int | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    if not isinstance(command, str) or not command.strip():
        return {"ok": False, "data": None, "meta": {}, "error": "command_required"}

    settings = config.load_settings()
    allowlist = [str(entry) for entry in settings.get("shell_allowlist", [])]
    if not approved and not is_allowlisted(command, allowlist):
        return {"ok": False, "data": None, "meta": {}, "error": "approval_required"}

    try:
        workdir = sandbox.resolve(cwd)
    except sandbox.SandboxError as exc:
        return {"ok": False, "data": None, "meta": {"status": exc.status}, "error": exc.code}

    timeout = int(timeout_s or settings.get("shell_timeout_s", 30))
    limit = int(settings.get("max_output_bytes", 65536))
    started = time.perf_counter()
    try:
        completed = subprocess.run(  # noqa: S602 - shell=True is the tool's purpose
            command,
            shell=True,
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
        "meta": {"ms": int((time.perf_counter() - started) * 1000), "cwd": sandbox.relative(workdir)},
        "error": None if completed.returncode == 0 else f"exit_{completed.returncode}",
    }
