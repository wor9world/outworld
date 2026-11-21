"""Named command snippets per project. Execution goes through the shell tool, so the
allowlist, approval flow and audit trail are the same ones (SPEC §4.7)."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from tools import registry

from .. import db, sandbox
from .tools import audit

router = APIRouter()


class CommandIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    template: str = Field(min_length=1, max_length=2000)
    params: list[str] = []


class CommandPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    template: str | None = Field(default=None, min_length=1, max_length=2000)
    params: list[str] | None = None


class RunIn(BaseModel):
    params: dict[str, str] = {}


def _get(conn: sqlite3.Connection, command_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM commands WHERE id = ?", (command_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "command not found")
    return row


def _public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "name": row["name"],
        "template": row["template"],
        "params": json.loads(row["params_json"]),
    }


def render(template: str, params: dict[str, str]) -> tuple[str, str | None]:
    result = template
    for key, value in params.items():
        result = result.replace("{{" + key + "}}", value)
    marker = result.find("{{")
    if marker >= 0:
        end = result.find("}}", marker)
        return result, result[marker + 2 : end] if end > 0 else result[marker + 2 :]
    return result, None


@router.get("/projects/{project_id}/commands")
def list_commands(
    project_id: str, conn: sqlite3.Connection = Depends(db.get_db)
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM commands WHERE project_id = ? ORDER BY created_at DESC", (project_id,)
    ).fetchall()
    return [_public(row) for row in rows]


@router.post("/projects/{project_id}/commands", status_code=201)
def create_command(
    project_id: str, body: CommandIn, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict[str, Any]:
    if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
        raise HTTPException(404, "project not found")
    command_id = db.new_id()
    conn.execute(
        "INSERT INTO commands (id, project_id, name, template, params_json, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (command_id, project_id, body.name.strip(), body.template,
         json.dumps(body.params, ensure_ascii=False), db.now_iso()),
    )
    conn.commit()
    return _public(_get(conn, command_id))


@router.patch("/commands/{command_id}")
def patch_command(
    command_id: str, body: CommandPatch, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict[str, Any]:
    _get(conn, command_id)
    data = body.model_dump(exclude_none=True)
    if "params" in data:
        data["params_json"] = json.dumps(data.pop("params"), ensure_ascii=False)
    if data:
        columns = ", ".join(f"{key} = ?" for key in data)
        conn.execute(
            f"UPDATE commands SET {columns} WHERE id = ?",
            (*data.values(), command_id),
        )
        conn.commit()
    return _public(_get(conn, command_id))


@router.delete("/commands/{command_id}", status_code=204)
def delete_command(command_id: str, conn: sqlite3.Connection = Depends(db.get_db)):
    _get(conn, command_id)
    conn.execute("DELETE FROM commands WHERE id = ?", (command_id,))
    conn.commit()
    return


@router.post("/commands/{command_id}/run")
def run_command(
    command_id: str, body: RunIn, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict[str, Any]:
    row = _get(conn, command_id)
    command, missing = render(row["template"], body.params)
    if missing:
        raise HTTPException(400, f"missing_param:{missing}")

    cwd = "."
    if row["project_id"]:
        project = conn.execute(
            "SELECT root_path FROM projects WHERE id = ?", (row["project_id"],)
        ).fetchone()
        if project is not None:
            cwd = project["root_path"] or "."

    started = time.perf_counter()
    result = registry.get_tool("shell")(command=command, cwd=cwd)
    elapsed = int((time.perf_counter() - started) * 1000)

    if result.get("error") == "approval_required":
        token = sandbox.mint(conn, "shell", {"command": command, "cwd": cwd})
        result["approval_token"] = token
        result["message"] = "approval_required"

    audit(
        conn,
        "shell",
        {"command": command, "cwd": cwd, "command_id": command_id},
        result,
        "ok" if result.get("ok") else "error",
        elapsed,
    )
    status = 409 if result.get("error") == "approval_required" else 200
    from fastapi.responses import JSONResponse

    return JSONResponse(result, status_code=status)
