"""Planner: a deterministic step skeleton for a goal (no model call)."""

from __future__ import annotations

from typing import Any

from .registry import register_tool


@register_tool(name="planner", description="Turn a goal into an ordered step skeleton")
def run(goal: str = "") -> dict[str, Any]:
    text = " ".join((goal or "").split())
    if not text:
        return {"ok": False, "data": None, "meta": {}, "error": "goal_required"}

    steps = [
        {
            "title": f"เก็บบริบท: {text}",
            "tool": "knowledge",
            "args": {"op": "search", "q": text, "limit": 5},
        },
        {
            "title": "กำหนดผลลัพธ์ที่วัดได้ 1-3 ข้อ",
            "tool": None,
            "args": {},
        },
        {
            "title": "แตกงานเป็นขั้นที่ทำเสร็จได้ในรอบเดียว",
            "tool": None,
            "args": {},
        },
        {
            "title": "ทำทีละขั้นและบันทึกผลทันที",
            "tool": None,
            "args": {},
        },
        {
            "title": f"ตรวจผลและเก็บเป็น note: {text}",
            "tool": "knowledge",
            "args": {"op": "create", "title": text, "body": "ผลการทำตามแผน"},
        },
    ]
    return {
        "ok": True,
        "data": {
            "goal": text,
            "steps": steps,
            "assumptions": ["ยังไม่ทราบบริบทของโปรเจกต์ จึงเริ่มจากการค้นคลังความรู้"],
        },
        "meta": {"steps": len(steps)},
        "error": None,
    }
