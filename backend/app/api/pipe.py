"""Pipe endpoints: route (dry run), run, rules, reload."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db, pipe

router = APIRouter()


class RouteIn(BaseModel):
    message: str = Field(min_length=1, max_length=20000)


class RunIn(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    chat_id: str | None = None


@router.post("/pipe/route")
def route_message(body: RouteIn) -> dict[str, Any]:
    return pipe.route(body.message)


@router.post("/pipe/run")
def run_pipe(body: RunIn, conn: sqlite3.Connection = Depends(db.get_db)) -> dict[str, Any]:
    return pipe.run(conn, body.message, chat_id=body.chat_id)


@router.get("/pipe/rules")
def list_rules() -> dict[str, Any]:
    try:
        loaded = pipe.reload()
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(500, f"rules_invalid: {exc}") from None
    return {
        "intents": [
            {"id": rule.id, "intent": rule.intent, "priority": rule.priority,
             "patterns": [c.get("regex") or c.get("contains") or "" for c in [*rule.all, *rule.any]]}
            for rule in pipe.rules()
        ],
        "plans": [{"intent": plan.intent, "steps": plan.steps} for plan in pipe.plans().values()],
        "counts": loaded,
    }


@router.post("/pipe/reload")
def reload_rules() -> dict[str, Any]:
    try:
        return pipe.reload()
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(400, f"rules_invalid: {exc}") from None
