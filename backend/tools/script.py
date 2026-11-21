"""`script` tool: user-authored scripts with a manifest, parameters and a timeout.

Layout::

    workspace/scripts/
      hello.py          source
      hello.json        {"description":…, "language":"python", "params":["who"]}

A script is a first-class tool: the agent sees one function per script
(``script__hello``) and the pipe can route to it (SPEC §14).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from app import config, sandbox

from .registry import register_tool

NAME_RE = re.compile(r"^[a-z0-9_-]{1,40}$")
PARAM_RE = re.compile(r"^[A-Za-z0-9_]{1,24}$")
EXTENSIONS = {"python": ".py", "javascript": ".js"}

DEFAULT_TIMEOUT = 20
SEED_DIR = Path(__file__).resolve().parents[1] / "data" / "seed_scripts"


def scripts_dir() -> Path:
    path = sandbox.workspace() / "scripts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_name(name: str) -> str:
    if not NAME_RE.match(name or ""):
        raise sandbox.SandboxError("invalid_script_name", 400)
    return name


def _locate(name: str) -> tuple[Path, Path, dict[str, Any]] | None:
    base = scripts_dir() / name
    for language, extension in EXTENSIONS.items():
        source = base.with_suffix(extension)
        manifest_path = base.with_suffix(".json")
        if source.exists() and manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                manifest = {"language": language, "params": [], "description": ""}
            manifest.setdefault("language", language)
            manifest.setdefault("params", [])
            return source, manifest_path, manifest
    return None


def _run(source: Path, language: str, args: list[str], timeout: int) -> dict[str, Any]:
    if language == "python":
        argv = [sys.executable, "-I", str(source), *args]
    elif language == "javascript":
        bun = shutil.which("bun")
        if bun is None:
            return {"ok": False, "data": None, "meta": {}, "error": "unsupported_language"}
        argv = [bun, str(source), *args]
    else:
        return {"ok": False, "data": None, "meta": {}, "error": "unsupported_language"}

    limit = int(config.load_settings().get("max_output_bytes", 65536))
    started = time.perf_counter()
    try:
        completed = subprocess.run(  # noqa: S603 - argv is built from a validated path
            argv,
            cwd=str(sandbox.workspace()),
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

    def cap(text: str) -> tuple[str, bool]:
        raw = text.encode("utf-8", errors="replace")
        if len(raw) <= limit:
            return text, False
        return raw[:limit].decode("utf-8", errors="ignore"), True

    stdout, out_cut = cap(completed.stdout)
    stderr, err_cut = cap(completed.stderr)
    return {
        "ok": completed.returncode == 0,
        "data": {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": completed.returncode,
            "truncated": out_cut or err_cut,
        },
        "meta": {"ms": int((time.perf_counter() - started) * 1000), "script": source.stem},
        "error": None if completed.returncode == 0 else f"exit_{completed.returncode}",
    }


def catalogue() -> list[dict[str, Any]]:
    """Manifest list for a project, used by the UI and the agent tool catalogue."""
    found: list[dict[str, Any]] = []
    for manifest_path in sorted(scripts_dir().glob("*.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = manifest_path.stem
        if not NAME_RE.match(name):
            continue
        found.append(
            {
                "name": name,
                "description": str(manifest.get("description", "")),
                "language": str(manifest.get("language", "python")),
                "params": [str(param) for param in manifest.get("params", [])],
            }
        )
    return found


def run_script(name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return run(op="run", name=name, params=params or {})


@register_tool(
    name="script",
    description="List, write, read, delete and run user scripts stored in workspace/scripts",
)
def run(
    op: str,
    name: str = "",
    source: str | None = None,
    description: str | None = None,
    language: str | None = None,
    params: list[str] | None = None,
    params_values: dict[str, Any] | None = None,
    timeout_s: int | None = None,
) -> dict[str, Any]:
    try:
        if op == "list":
            return {"ok": True, "data": {"scripts": catalogue()}, "meta": {}, "error": None}

        if op == "seed":
            installed: list[str] = []
            skipped: list[str] = []
            for manifest_path in sorted(SEED_DIR.glob("*.json")):
                name = manifest_path.stem
                if not NAME_RE.match(name):
                    continue
                if _locate(name) is not None:
                    skipped.append(name)
                    continue
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                language = str(manifest.get("language", "python"))
                extension = EXTENSIONS.get(language, ".py")
                source_path = manifest_path.with_suffix(extension)
                if not source_path.exists():
                    continue
                (scripts_dir() / f"{name}{extension}").write_text(
                    source_path.read_text(encoding="utf-8"), encoding="utf-8"
                )
                (scripts_dir() / f"{name}.json").write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                installed.append(name)
            return {
                "ok": True,
                "data": {"installed": installed, "skipped": skipped},
                "meta": {"source": str(SEED_DIR)},
                "error": None,
            }

        safe = _validate_name(name)

        if op == "read":
            found = _locate(safe)
            if found is None:
                return {"ok": False, "data": None, "meta": {}, "error": "not_found"}
            path, _, manifest = found
            return {
                "ok": True,
                "data": {"source": path.read_text(encoding="utf-8"), "manifest": manifest},
                "meta": {},
                "error": None,
            }

        if op == "write":
            if source is None:
                return {"ok": False, "data": None, "meta": {}, "error": "source_required"}
            chosen = language or "python"
            if chosen not in EXTENSIONS:
                return {"ok": False, "data": None, "meta": {}, "error": "unsupported_language"}
            declared = list(params or [])
            for param in declared:
                if not PARAM_RE.match(str(param)):
                    return {
                        "ok": False, "data": None, "meta": {},
                        "error": f"invalid_param:{param}",
                    }
            base = scripts_dir() / safe
            for extension in EXTENSIONS.values():
                stale = base.with_suffix(extension)
                if stale.exists() and extension != EXTENSIONS[chosen]:
                    stale.unlink()
            target = base.with_suffix(EXTENSIONS[chosen])
            target.write_text(source, encoding="utf-8")
            manifest = {
                "description": description or "",
                "language": chosen,
                "params": declared,
                "timeout_s": int(timeout_s or DEFAULT_TIMEOUT),
            }
            base.with_suffix(".json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return {
                "ok": True,
                "data": {"name": safe, "path": sandbox.relative(target), "manifest": manifest},
                "meta": {},
                "error": None,
            }

        if op == "delete":
            found = _locate(safe)
            if found is None:
                return {"ok": False, "data": None, "meta": {}, "error": "not_found"}
            path, manifest_path, _ = found
            path.unlink()
            manifest_path.unlink()
            return {"ok": True, "data": {"deleted": safe}, "meta": {}, "error": None}

        if op == "run":
            found = _locate(safe)
            if found is None:
                return {"ok": False, "data": None, "meta": {}, "error": "not_found"}
            path, _, manifest = found
            values: list[str] = []
            supplied = params_values or {}
            for param in manifest.get("params", []):
                value = supplied.get(param)
                if value is None or value == "":
                    return {
                        "ok": False, "data": None, "meta": {},
                        "error": f"missing_param:{param}",
                    }
                values.append(str(value))
            timeout = int(
                manifest.get("timeout_s")
                or config.load_settings().get("code_timeout_s", DEFAULT_TIMEOUT)
            )
            return _run(path, str(manifest.get("language", "python")), values, timeout)

        return {"ok": False, "data": None, "meta": {}, "error": f"unknown_op:{op}"}
    except sandbox.SandboxError as exc:
        return {"ok": False, "data": None, "meta": {"status": exc.status}, "error": exc.code}
