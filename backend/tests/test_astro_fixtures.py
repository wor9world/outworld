"""T11 — the copied astro module: pinned fixtures plus independent constants."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def astro(client, **args):
    return client.post("/api/tools/astro", json=args)


def test_registered_as_astro(client) -> None:
    assert "astro" in client.get("/api/health").json()["tools"]


def test_j2000_sun_and_houses(client) -> None:
    body = astro(
        client,
        birth_date="2000-01-01",
        birth_time="12:00",
        lat=0.0,
        lon=0.0,
        tz_offset=0,
        systems=["western", "india"],
    ).json()
    assert body["ok"] is True

    western = body["data"]["western"]
    sun = western["planets"]["Sun"]["lon"]
    # Independent astronomical constant: the Sun at J2000 is ~280.37 deg.
    assert abs(sun - 280.3689) < 0.01
    assert abs(sun - load("astro_j2000.json")["sun_lon"]) < 1e-6
    assert len(western["houses"]) == 12
    assert western["ascendant"]["lon"] > 0

    # Lahiri ayanamsa in 2000 is ~23.85 deg.
    ayanamsa = body["data"]["india"]["ayanamsa_deg"]
    assert abs(ayanamsa - 23.85) < 0.05


def test_yala_full_chart(client) -> None:
    body = astro(client, birth_date="1992-08-08", birth_time="16:49", location="ยะลา").json()
    assert body["ok"] is True
    fixture = load("astro_yala.json")
    data = body["data"]
    assert data["input_resolved"]["local_time"] == fixture["local_time"]
    assert data["input_resolved"]["utc_time"] == fixture["utc_time"]
    assert abs(data["western"]["planets"]["Sun"]["lon"] - fixture["sun"]) < 1e-6
    assert abs(data["western"]["planets"]["Moon"]["lon"] - fixture["moon"]) < 1e-6
    assert data["bazi"]["pillars"]["day"]["chinese"] == fixture["day_pillar"]
    assert data["humandesign"]["type"] == fixture["hd_type"]
    for system in ("bazi", "india", "western", "humandesign"):
        assert system in data


def test_thai_buddhist_era_input(client) -> None:
    body = astro(
        client,
        birth_date="17/08/2538",
        birth_time="14:30",
        location="Bangkok",
        systems=["western"],
    ).json()
    fixture = load("astro_2538.json")
    assert body["data"]["input_resolved"]["local_time"] == fixture["local_time"]
    assert body["data"]["input_resolved"]["utc_time"] == fixture["utc_time"]
    assert abs(body["data"]["western"]["planets"]["Sun"]["lon"] - fixture["sun"]) < 1e-6


def test_unknown_location_is_an_envelope_not_a_crash(client) -> None:
    body = astro(client, birth_date="2000-01-01", location="Atlantis-nowhere").json()
    assert body["ok"] is False
    assert "ไม่พบข้อมูลพิกัด" in body["error"]


def test_module_main_prints_json(client) -> None:
    """The copied file keeps its own __main__ block; it must exit cleanly."""
    result = subprocess.run(
        [sys.executable, "-m", "tools.astro"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    payload = json.loads(result.stdout)
    assert "ok" in payload and "data" in payload
