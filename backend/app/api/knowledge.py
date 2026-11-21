"""Knowledge notes: CRUD plus FTS5 search."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db
from tools import knowledge as store

router = APIRouter()


class NoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = ""
    tags: str = ""
    project_id: str | None = None


class NotePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None
    tags: str | None = None


@router.get("/knowledge")
def list_notes(
    q: str | None = None,
    project_id: str | None = None,
    limit: int = 50,
    snippets: int = 0,
    conn: sqlite3.Connection = Depends(db.get_db),
) -> list[dict]:
    return store.search(conn, q, project_id, limit, snippets=bool(snippets))


@router.post("/knowledge", status_code=201)
def create_note(body: NoteIn, conn: sqlite3.Connection = Depends(db.get_db)) -> dict:
    return store.create(conn, body.title, body.body, body.tags, body.project_id)


@router.get("/knowledge/{note_id}")
def get_note(note_id: str, conn: sqlite3.Connection = Depends(db.get_db)) -> dict:
    note = store.get(conn, note_id)
    if note is None:
        raise HTTPException(404, "note not found")
    return note


@router.patch("/knowledge/{note_id}")
def patch_note(
    note_id: str, body: NotePatch, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict:
    note = store.update(conn, note_id, body.title, body.body, body.tags)
    if note is None:
        raise HTTPException(404, "note not found")
    return note


@router.delete("/knowledge/{note_id}", status_code=204)
def delete_note(note_id: str, conn: sqlite3.Connection = Depends(db.get_db)):
    if not store.delete(conn, note_id):
        raise HTTPException(404, "note not found")
    return None
