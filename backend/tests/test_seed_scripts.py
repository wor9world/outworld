"""Seed scripts: the starter set must install and actually run."""

from __future__ import annotations

from pathlib import Path

SEEDS = {
    "tree",
    "project_report",
    "todo_scan",
    "db_stats",
    "daily_note",
    "csv_summary",
    "astro_text",
}


def script(client, **args):
    return client.post("/api/tools/script", json=args)


def seed(client):
    body = script(client, op="seed").json()
    assert body["ok"] is True, body
    return body["data"]


def test_seed_installs_the_starter_set(client) -> None:
    data = seed(client)
    assert set(data["installed"]) == SEEDS
    assert data["skipped"] == []


def test_seed_is_idempotent(client) -> None:
    seed(client)
    again = seed(client)
    assert again["installed"] == []
    assert set(again["skipped"]) == SEEDS


def test_every_seed_has_a_manifest_with_a_description(client) -> None:
    seed(client)
    rows = script(client, op="list").json()["data"]["scripts"]
    assert {row["name"] for row in rows} == SEEDS
    for row in rows:
        assert row["description"], row["name"]
        assert row["language"] == "python"


def test_tree_runs(client) -> None:
    seed(client)
    body = script(client, op="run", name="tree").json()
    assert body["ok"] is True, body
    assert "total:" in body["data"]["stdout"]


def test_project_report_runs(client) -> None:
    seed(client)
    body = script(client, op="run", name="project_report").json()
    assert body["ok"] is True, body
    assert "files" in body["data"]["stdout"]
    assert "lines" in body["data"]["stdout"]


def test_todo_scan_runs(client) -> None:
    seed(client)
    body = script(client, op="run", name="todo_scan").json()
    assert body["ok"] is True, body
    assert "marker(s)" in body["data"]["stdout"]


def test_db_stats_reads_the_live_database(client) -> None:
    seed(client)
    body = script(client, op="run", name="db_stats").json()
    assert body["ok"] is True, body
    assert "schema" in body["data"]["stdout"]
    assert "runs" in body["data"]["stdout"]


def test_daily_note_creates_today_file(client, workspace) -> None:
    seed(client)
    body = script(client, op="run", name="daily_note").json()
    assert body["ok"] is True, body
    created = list((workspace / "notes").glob("*.md"))
    assert len(created) == 1
    assert "เป้าหมายวันนี้" in created[0].read_text(encoding="utf-8")


def test_csv_summary_with_param(client, workspace) -> None:
    seed(client)
    (workspace / "sample.csv").write_text(
        "name,amount\napple,1.5\nbanana,\ncherry,3\n", encoding="utf-8"
    )
    body = script(client, op="run", name="csv_summary", params_values={"file": "sample.csv"}).json()
    assert body["ok"] is True, body
    out = body["data"]["stdout"]
    assert "rows    : 3" in out
    assert "1.5" in out
    assert "3" in out
    assert "amount" in out


def test_csv_summary_requires_its_param(client) -> None:
    seed(client)
    body = script(client, op="run", name="csv_summary").json()
    assert body["error"] == "missing_param:file"


def test_astro_text_is_installed_with_one_param(client) -> None:
    seed(client)
    rows = {row["name"]: row for row in script(client, op="list").json()["data"]["scripts"]}
    assert rows["astro_text"]["params"] == ["birth_date"]


def test_seed_sources_are_stdlib_only() -> None:
    """A seed script may not depend on a package the venv does not guarantee."""
    root = Path(__file__).resolve().parents[1] / "data" / "seed_scripts"
    allowed = {
        "csv", "json", "os", "pathlib", "re", "sqlite3", "subprocess",
        "sys", "time", "datetime", "urllib", "collections", "textwrap",
    }
    for path in root.glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(("import ", "from ")) and "__future__" not in line:
                module = line.split()[1].split(".")[0]
                assert module in allowed, f"{path.name}: unexpected import {module}"
