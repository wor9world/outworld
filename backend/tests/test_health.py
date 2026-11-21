"""T1 — health, schema, settings bootstrap."""

from __future__ import annotations

from app import config, db


def test_health_shape(client) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["python"].startswith("3.15")
    assert body["schema"] == 1
    assert body["llm"] == "disabled"
    assert isinstance(body["tools"], list)
    assert body["version"] == "2.0.0"


def test_db_created_with_all_tables(client) -> None:
    conn = db.connect()
    try:
        names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
            )
        }
        for expected in (
            "projects",
            "chats",
            "messages",
            "knowledge",
            "knowledge_fts",
            "providers",
            "commands",
            "tool_calls",
            "approvals",
            "runs",
            "patterns",
            "pattern_fts",
            "feedback",
        ):
            assert expected in names, expected
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_settings_file_is_written(client) -> None:
    settings = config.load_settings()
    assert settings["shell_timeout_s"] == 30
    assert config.settings_path().exists()
    assert config.workspace_root().exists()


def test_settings_survive_corruption(client) -> None:
    path = config.settings_path()
    path.write_text("{not json", encoding="utf-8")
    settings = config.load_settings()
    assert settings["code_timeout_s"] == 20
