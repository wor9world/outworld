"""`fs` tool: read, write, list, patch inside the workspace."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app import config, sandbox

from .registry import register_tool

SKIP = {".git", "node_modules", ".venv", "__pycache__"}


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise sandbox.SandboxError("not_found", 404)
    limit = int(config.load_settings().get("max_output_bytes", 65536))
    raw = path.read_bytes()
    truncated = len(raw) > limit
    text = raw[:limit].decode("utf-8", errors="replace")
    return {"content": text, "bytes": len(raw), "truncated": truncated}


def _write(path: Path, content: str) -> dict[str, Any]:
    sandbox.ensure_parent(path)
    data = content.encode("utf-8")
    path.write_bytes(data)
    return {"path": sandbox.relative(path), "bytes": len(data)}


def _list(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise sandbox.SandboxError("not_found", 404)
    if not path.is_dir():
        raise sandbox.SandboxError("not_a_directory", 400)
    entries = []
    for child in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if child.name in SKIP:
            continue
        entries.append(
            {
                "name": child.name,
                "type": "dir" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else None,
            }
        )
    return {"entries": entries}


def _patch(path: Path, old: str, new: str) -> dict[str, Any]:
    if not path.is_file():
        raise sandbox.SandboxError("not_found", 404)
    text = path.read_text(encoding="utf-8", errors="replace")
    count = text.count(old)
    if count != 1:
        raise sandbox.SandboxError("ambiguous_patch" if count else "patch_target_missing",
                                   409 if count else 404)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return {"path": sandbox.relative(path), "bytes": len(path.read_bytes())}


@register_tool(name="fs", description="Read, write, list and patch files inside the workspace")
def run(
    op: str,
    path: str = ".",
    content: str | None = None,
    old: str | None = None,
    new: str | None = None,
) -> dict[str, Any]:
    try:
        target = sandbox.resolve(path)
        if op == "read":
            data = _read(target)
        elif op == "write":
            if content is None:
                return {"ok": False, "data": None, "meta": {}, "error": "content_required"}
            data = _write(target, content)
        elif op == "list":
            data = _list(target)
        elif op == "patch":
            if old is None or new is None:
                return {"ok": False, "data": None, "meta": {}, "error": "old_and_new_required"}
            data = _patch(target, old, new)
        else:
            return {"ok": False, "data": None, "meta": {}, "error": f"unknown_op:{op}"}
    except sandbox.SandboxError as exc:
        return {"ok": False, "data": None, "meta": {"status": exc.status}, "error": exc.code}
    except OSError as exc:
        return {"ok": False, "data": None, "meta": {}, "error": f"os_error:{exc.strerror}"}
    return {"ok": True, "data": data, "meta": {"op": op}, "error": None}
