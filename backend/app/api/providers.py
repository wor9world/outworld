"""Provider CRUD. The API key is write-only: it is never serialised back."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db, llm

router = APIRouter()

PUBLIC = "id, name, kind, base_url, model, enabled, created_at"


class ProviderIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: str = Field(pattern="^(openai|ollama)$")
    base_url: str = Field(min_length=1, max_length=300)
    model: str = Field(min_length=1, max_length=120)
    api_key: str = ""
    enabled: bool = False


class ProviderPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    kind: str | None = Field(default=None, pattern="^(openai|ollama)$")
    base_url: str | None = Field(default=None, min_length=1, max_length=300)
    model: str | None = Field(default=None, min_length=1, max_length=120)
    api_key: str | None = None
    enabled: bool | None = None


def _get(conn: sqlite3.Connection, provider_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM providers WHERE id = ?", (provider_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "provider not found")
    return row


def _public(row: sqlite3.Row) -> dict:
    data = dict(row)
    data.pop("api_key", None)
    data["enabled"] = bool(data["enabled"])
    return data


@router.get("/providers")
def list_providers(conn: sqlite3.Connection = Depends(db.get_db)) -> list[dict]:
    rows = conn.execute(f"SELECT {PUBLIC} FROM providers ORDER BY created_at").fetchall()
    return [{**dict(row), "enabled": bool(row["enabled"])} for row in rows]


@router.post("/providers", status_code=201)
def create_provider(
    body: ProviderIn, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict:
    provider_id = db.new_id()
    conn.execute(
        "INSERT INTO providers (id, name, kind, base_url, model, api_key, enabled, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            provider_id,
            body.name.strip(),
            body.kind,
            body.base_url.strip().rstrip("/"),
            body.model.strip(),
            body.api_key,
            int(body.enabled),
            db.now_iso(),
        ),
    )
    conn.commit()
    return _public(_get(conn, provider_id))


@router.patch("/providers/{provider_id}")
def patch_provider(
    provider_id: str, body: ProviderPatch, conn: sqlite3.Connection = Depends(db.get_db)
) -> dict:
    _get(conn, provider_id)
    data = body.model_dump(exclude_none=True)
    if "api_key" in data and data["api_key"] == "":
        data.pop("api_key")  # empty key keeps the stored one
    if "enabled" in data:
        data["enabled"] = int(bool(data["enabled"]))
    if data:
        columns = ", ".join(f"{key} = ?" for key in data)
        conn.execute(
            f"UPDATE providers SET {columns} WHERE id = ?",
            (*data.values(), provider_id),
        )
        conn.commit()
    return _public(_get(conn, provider_id))


@router.delete("/providers/{provider_id}", status_code=204)
def delete_provider(provider_id: str, conn: sqlite3.Connection = Depends(db.get_db)):
    _get(conn, provider_id)
    conn.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
    conn.commit()
    return


@router.post("/providers/{provider_id}/test")
def probe_provider(provider_id: str, conn: sqlite3.Connection = Depends(db.get_db)) -> dict:
    return llm.probe(dict(_get(conn, provider_id)))
