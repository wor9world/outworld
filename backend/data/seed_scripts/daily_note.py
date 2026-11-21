"""daily_note — สร้างโน้ตของวันนี้ใน notes/YYYY-MM-DD.md ถ้ายังไม่มี

ใช้: python daily_note.py [title]
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

TEMPLATE = """# {day}

## เป้าหมายวันนี้
- [ ]

## บันทึก

## พรุ่งนี้
- [ ]
"""


def main() -> int:
    today = date.today().isoformat()
    title = " ".join(sys.argv[1:]).strip()
    notes = Path("notes")
    notes.mkdir(parents=True, exist_ok=True)
    target = notes / f"{today}.md"

    if target.exists():
        print(f"exists: {target}")
    else:
        header = f"# {today}" + (f" - {title}" if title else "")
        body = TEMPLATE.format(day=today).replace(f"# {today}", header, 1)
        target.write_text(body, encoding="utf-8")
        print(f"created: {target}")

    print(f"path: {target.resolve()}")
    print(target.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
