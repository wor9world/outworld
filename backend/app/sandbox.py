"""Workspace sandbox: every path a tool touches is resolved here first."""

from __future__ import annotations

from pathlib import Path

from . import config


class SandboxError(Exception):
    """A request that must be refused with a specific error code."""

    def __init__(self, code: str, status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


def workspace() -> Path:
    root = config.workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def resolve(relative: str) -> Path:
    """Resolve ``relative`` inside the workspace or raise ``SandboxError``."""
    root = workspace()
    raw = (relative or ".").replace("\\", "/")
    target = (root / raw).resolve()
    if target != root and not target.is_relative_to(root):
        raise SandboxError("outside_workspace", 403)
    return target


def relative(path: Path) -> str:
    return path.resolve().relative_to(workspace()).as_posix()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
