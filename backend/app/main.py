"""FastAPI application factory.

Tools register themselves on import; a module that does not exist yet is skipped so
the app is runnable while the tool layer is still being built.
"""

from __future__ import annotations

import importlib
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config, db
from .api import calls, chats, health, knowledge, projects, tools as tools_api

TOOL_MODULES = (
    "astro",
    "calc",
    "code",
    "fs",
    "knowledge",
    "memory",
    "planner",
    "project",
    "search",
    "shell",
    "z3",
)


def load_tools() -> list[str]:
    """Import every tool module that exists and return the ones loaded."""
    loaded: list[str] = []
    for name in TOOL_MODULES:
        try:
            importlib.import_module(f"tools.{name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"tools.{name}":
                continue
            raise
        loaded.append(name)
    astro = sys.modules.get("tools.astro")
    if astro is not None:
        astro.set_ephe_path(str(config.ephe_dir()))
    return loaded


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    config.ensure_dirs()
    db.init_db()
    load_tools()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Outworld Workbench", version=health.VERSION, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Every error leaves the process as {"message": "..."} (SPEC §5)."""
        return JSONResponse({"message": str(exc.detail)}, status_code=exc.status_code)

    app.include_router(health.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")
    app.include_router(chats.router, prefix="/api")
    app.include_router(knowledge.router, prefix="/api")
    app.include_router(tools_api.router, prefix="/api")
    app.include_router(calls.router, prefix="/api")
    return app


app = create_app()
