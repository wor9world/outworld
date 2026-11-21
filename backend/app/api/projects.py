"""Projects: CRUD plus the aggregate view the project page needs."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import config, db

router = APIRouter()


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    root_path: str = "."
    instructions: str = ""


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    root_path: str | None = None
    instructions: str | None = None


def normalize_root(root_path: str) -> str:
    """Keep root_path relative and inside the workspace."""
    path = Path(root_path.replace("\\", "/"))
    if path.is_absolute():
        raise HTTPException(400, "root_path must be relative")
    root = config.workspace_root().resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(400, "root_path escapes workspace")
    return path.as_posix() or "."


def valid_id(value: str) -> str:
    if not value or len(value) > 64 or not all(c.isalnum() or c in "-_" for c in value):
        raise HTTPException(404, "unknown id")
    return value


@router.get("/projects")
def list_projects(conn: sqlite3.Connection = Depends(db.get_db)) -> list[dict]:
    rows = conn.execute(
        """
        SELECT p.id, p.name, p.root_path, p.updated_at,
               (SELECT COUNT(*) FROM chats c WHERE c.project_id = p.id) AS chat_count
        FROM projects p
        ORDER BY p.updated_at DESC
        """
    ).fetchall()
    return db.to_dicts(rows)


@router.post("/projects", status_code=201)
def create_project(
    body: ProjectIn, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict:
    project_id = db.new_id()
    now = db.now_iso()
    conn.execute(
        "INSERT INTO projects (id, name, root_path, instructions, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (project_id, body.name.strip(), normalize_root(body.root_path), body.instructions, now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return dict(row)


@router.get("/projects/{project_id}")
def get_project(
    project_id: str, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict:
    valid_id(project_id)
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if project is None:
        raise HTTPException(404, "project not found")
    chats = db.to_dicts(
        conn.execute(
            "SELECT id, title, updated_at,"
            " (SELECT COUNT(*) FROM messages m WHERE m.chat_id = c.id) AS message_count"
            " FROM chats c WHERE project_id = ? ORDER BY updated_at DESC",
            (project_id,),
        ).fetchall()
    )
    notes = db.to_dicts(
        conn.execute(
            "SELECT id, title, tags, updated_at FROM knowledge WHERE project_id = ?"
            " ORDER BY updated_at DESC",
            (project_id,),
        ).fetchall()
    )
    commands = db.to_dicts(
        conn.execute(
            "SELECT id, name, template, params_json FROM commands WHERE project_id = ?"
            " ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    )
    return {"project": dict(project), "chats": chats, "notes": notes, "commands": commands}


@router.patch("/projects/{project_id}")
def update_project(
    project_id: str, body: ProjectPatch, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict:
    valid_id(project_id)
    current = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if current is None:
        raise HTTPException(404, "project not found")
    data = body.model_dump(exclude_none=True)
    if "root_path" in data:
        data["root_path"] = normalize_root(data["root_path"])
    if not data:
        return dict(current)
    data["updated_at"] = db.now_iso()
    columns = ", ".join(f"{key} = ?" for key in data)
    conn.execute(
        f"UPDATE projects SET {columns} WHERE id = ?",
        (*data.values(), project_id),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, conn: sqlite3.Connection = Depends(db.get_db)):
    valid_id(project_id)
    cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(404, "project not found")
    return
