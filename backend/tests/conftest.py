"""Shared pytest fixtures: an isolated data dir and a FastAPI test client."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


@pytest.fixture(scope="session", autouse=True)
def _env(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    root = tmp_path_factory.mktemp("outworld")
    os.environ["OUTWORLD_DATA"] = str(root / "data")
    os.environ["OUTWORLD_DB"] = str(root / "data" / "outworld.db")
    os.environ["OUTWORLD_WORKSPACE"] = str(root / "workspace")
    os.environ["OUTWORLD_EPHE"] = str(BACKEND / "data" / "assets")
    yield root


@pytest.fixture()
def root(_env: Path) -> Path:
    return _env


@pytest.fixture()
def client() -> Iterator[object]:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _clean_db(client) -> Iterator[None]:
    """Every test starts from an empty database (triggers keep FTS in sync)."""
    yield
    from app import db

    conn = db.connect()
    try:
        for table in (
            "feedback",
            "patterns",
            "runs",
            "approvals",
            "tool_calls",
            "commands",
            "providers",
            "knowledge",
            "messages",
            "chats",
            "projects",
        ):
            conn.execute(f"DELETE FROM {table}")  # noqa: S608 - fixed table list
        conn.execute("DELETE FROM sqlite_sequence")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def workspace(root: Path) -> Path:
    path = root / "workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path
