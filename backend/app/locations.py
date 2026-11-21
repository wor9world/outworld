"""Extra location coordinates for the astro tool.

``tools/astro.py`` is a byte-identical copy and must not be edited. Its built-in table
does not cover every Thai province, and geopy is intentionally not installed. This
module fills the gap: the API resolves a name here and passes lat/lon to the tool.

Coordinates are approximate city/province centres (three decimals is ~100 m), which is
more than enough for a natal chart.
"""

from __future__ import annotations

TH: dict[str, tuple[float, float, str]] = {
    "ยะลา": (6.5410, 101.2803, "Asia/Bangkok"),
    "yala": (6.5410, 101.2803, "Asia/Bangkok"),
    "ปัตตานี": (6.8696, 101.2504, "Asia/Bangkok"),
    "pattani": (6.8696, 101.2504, "Asia/Bangkok"),
    "นราธิวาส": (6.4255, 101.8253, "Asia/Bangkok"),
    "narathiwat": (6.4255, 101.8253, "Asia/Bangkok"),
    "สตูล": (6.6238, 100.0674, "Asia/Bangkok"),
    "satun": (6.6238, 100.0674, "Asia/Bangkok"),
    "ตรัง": (7.5593, 99.6114, "Asia/Bangkok"),
    "trang": (7.5593, 99.6114, "Asia/Bangkok"),
    "พัทลุง": (7.6167, 100.0833, "Asia/Bangkok"),
    "phatthalung": (7.6167, 100.0833, "Asia/Bangkok"),
    "สุราษฎร์ธานี": (9.1382, 99.3215, "Asia/Bangkok"),
    "surat thani": (9.1382, 99.3215, "Asia/Bangkok"),
    "นครศรีธรรมราช": (8.4304, 99.9631, "Asia/Bangkok"),
    "nakhon si thammarat": (8.4304, 99.9631, "Asia/Bangkok"),
    "ระยอง": (12.6814, 101.2815, "Asia/Bangkok"),
    "rayong": (12.6814, 101.2815, "Asia/Bangkok"),
    "เชียงใหม่": (18.7883, 98.9853, "Asia/Bangkok"),  # also in the module's table
    "ลำปาง": (18.2888, 99.4909, "Asia/Bangkok"),
    "lampang": (18.2888, 99.4909, "Asia/Bangkok"),
    "พิษณุโลก": (16.8211, 100.2659, "Asia/Bangkok"),
    "phitsanulok": (16.8211, 100.2659, "Asia/Bangkok"),
    "นครสวรรค์": (15.7030, 100.1372, "Asia/Bangkok"),
    "nakhon sawan": (15.7030, 100.1372, "Asia/Bangkok"),
    "ร้อยเอ็ด": (16.0538, 103.6520, "Asia/Bangkok"),
    "roi et": (16.0538, 103.6520, "Asia/Bangkok"),
    "สกลนคร": (17.1546, 104.1348, "Asia/Bangkok"),
    "sakon nakhon": (17.1546, 104.1348, "Asia/Bangkok"),
}


def resolve(name: str | None) -> tuple[float, float, str] | None:
    if not name:
        return None
    key = " ".join(name.strip().lower().split())
    if key in TH:
        return TH[key]
    for candidate, value in TH.items():
        if candidate in key:
            return value
    return None
