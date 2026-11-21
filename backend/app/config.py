"""Configuration: environment variables plus data/settings.json.

Every path is resolved on call, never cached, so tests can point the process at a
temporary directory by setting the environment before a request.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SETTINGS: dict[str, Any] = {
    "workspace_root": str(ROOT / "workspace"),
    "shell_allowlist": ["echo", "ls", "dir", "pwd", "git status", "git diff", "git log"],
    "shell_timeout_s": 30,
    "code_timeout_s": 20,
    "max_output_bytes": 65536,
    "llm_max_iterations": 8,
    "theme": "system",
    "web_search": {"enabled": False, "provider": "brave", "api_key": None},
}

DEFAULT_CORS = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:3000,http://127.0.0.1:3000"
)


def data_dir() -> Path:
    return Path(os.environ.get("OUTWORLD_DATA", str(ROOT / "data")))


def db_path() -> Path:
    return Path(os.environ.get("OUTWORLD_DB", str(data_dir() / "outworld.db")))


def workspace_root() -> Path:
    return Path(os.environ.get("OUTWORLD_WORKSPACE", str(ROOT / "workspace")))


def ephe_dir() -> Path:
    return Path(os.environ.get("OUTWORLD_EPHE", str(ROOT / "backend" / "data" / "assets")))


def cors_origins() -> list[str]:
    raw = os.environ.get("OUTWORLD_CORS", DEFAULT_CORS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def settings_path() -> Path:
    return data_dir() / "settings.json"


def ensure_dirs() -> None:
    data_dir().mkdir(parents=True, exist_ok=True)
    workspace_root().mkdir(parents=True, exist_ok=True)


def save_settings(settings: dict[str, Any]) -> None:
    ensure_dirs()
    settings_path().write_text(
        json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_settings() -> dict[str, Any]:
    """Read settings.json, falling back to defaults on a missing or corrupt file."""
    ensure_dirs()
    merged: dict[str, Any] = json.loads(json.dumps(DEFAULT_SETTINGS))
    path = settings_path()
    if not path.exists():
        save_settings(merged)
        return merged
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        save_settings(merged)
        return merged
    if isinstance(raw, dict):
        merged.update(raw)
    return merged
