"""astro_text — ดวงแบบข้อความบรรทัดเดียว ผ่าน API ของ Outworld

ใช้: python astro_text.py <YYYY-MM-DD> [HH:MM] [location]
ค่าเริ่มต้น: HH:MM=12:00, location=Bangkok
ต้องเปิด backend ที่ http://127.0.0.1:8000 ก่อน
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8000/api/tools/astro"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: astro_text.py <YYYY-MM-DD> [HH:MM] [location]")
        return 2
    birth_date = sys.argv[1]
    birth_time = sys.argv[2] if len(sys.argv) > 2 else "12:00"
    location = sys.argv[3] if len(sys.argv) > 3 else "Bangkok"

    payload = json.dumps(
        {"birth_date": birth_date, "birth_time": birth_time, "location": location}
    ).encode("utf-8")
    request = urllib.request.Request(
        URL, data=payload, headers={"content-type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"backend unreachable: {exc}")
        return 2

    if not body.get("ok"):
        print(f"error: {body.get('error')}")
        return 1

    data = body["data"]
    western = data.get("western") or {}
    planets = western.get("planets") or {}
    ascendant = western.get("ascendant") or {}
    day = ((data.get("bazi") or {}).get("pillars") or {}).get("day") or {}
    resolved = data.get("input_resolved") or {}

    parts = [str(resolved.get("local_time", "")).replace("T", " ")[:16]]
    for name in ("Sun", "Moon"):
        planet = planets.get(name)
        if planet:
            parts.append(f"{name} {planet.get('degree')} {planet.get('sign')}")
    if ascendant.get("degree"):
        parts.append(f"Asc {ascendant.get('degree')} {ascendant.get('sign')}")
    if day.get("chinese"):
        parts.append(f"BaZi {day['chinese']}")

    print(" · ".join(part for part in parts if part))
    print(f"location: {resolved.get('location')} (lat {resolved.get('lat')}, lon {resolved.get('lon')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
