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


# --- approvals -------------------------------------------------------------

APPROVAL_TTL_S = 600


def mint(conn, tool: str, args: dict) -> str:
    """Insert a pending approval and return its single-use token."""
    import json
    import secrets
    from datetime import UTC, datetime, timedelta

    token = "ap-" + secrets.token_hex(5)
    now = datetime.now(UTC)
    conn.execute(
        "INSERT INTO approvals (token, tool, args_json, status, created_at, expires_at)"
        " VALUES (?, ?, ?, 'pending', ?, ?)",
        (
            token,
            tool,
            json.dumps(args, ensure_ascii=False, default=str),
            now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            (now + timedelta(seconds=APPROVAL_TTL_S)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        ),
    )
    conn.commit()
    return token


def read_approval(conn, token: str) -> dict | None:
    row = conn.execute("SELECT * FROM approvals WHERE token = ?", (token,)).fetchone()
    return dict(row) if row is not None else None


def expire_if_needed(conn, row: dict) -> dict:
    from datetime import UTC, datetime

    if row["status"] != "pending":
        return row
    try:
        expires = datetime.strptime(row["expires_at"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    except ValueError:
        return row
    if datetime.now(UTC) > expires:
        conn.execute("UPDATE approvals SET status = 'expired' WHERE token = ?", (row["token"],))
        conn.commit()
        row = {**row, "status": "expired"}
    return row


def decide(conn, token: str, decision: str) -> tuple[str, dict | None]:
    """Transition an approval. Returns (status, executed_result)."""
    row = read_approval(conn, token)
    if row is None:
        raise SandboxError("approval_not_found", 404)
    row = expire_if_needed(conn, row)
    if row["status"] in ("approved", "denied", "expired"):
        raise SandboxError("approval_" + row["status"], 410)
    status = "approved" if decision == "approve" else "denied"
    conn.execute("UPDATE approvals SET status = ? WHERE token = ?", (status, token))
    conn.commit()
    return status, row
