"""todo_scan — หา TODO/FIXME/XXX/HACK ทั้ง workspace พร้อมอายุไฟล์

ใช้: python todo_scan.py [path]
ค่าเริ่มต้น: path="."
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

SKIP = {".git", "node_modules", ".venv", "__pycache__", ".svelte-kit", "build", "dist", ".pytest-tmp"}
MARKERS = ("TODO", "FIXME", "XXX", "HACK")


def age_days(path: Path) -> int:
    try:
        return int((time.time() - path.stat().st_mtime) / 86400)
    except OSError:
        return -1


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    if not root.exists():
        print(f"not found: {root}")
        return 2

    hits = 0
    for path in sorted(root.rglob("*")):
        if any(part in SKIP for part in path.parts) or not path.is_file():
            continue
        if path.stat().st_size > 1_048_576:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            marker = next((m for m in MARKERS if m in line), None)
            if marker is None:
                continue
            hits += 1
            snippet = line.strip()[:100]
            print(f"{path.relative_to(root)}:{number}  [{marker}]  {snippet}")

    print(f"\n{hits} marker(s) in {root.resolve()}")
    stale = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and not any(part in SKIP for part in path.parts)
        and age_days(path) >= 30
    ]
    if stale:
        print(f"\nไฟล์ไม่ได้แตะเกิน 30 วัน: {len(stale)}")
        for path in sorted(stale, key=lambda p: -age_days(p))[:10]:
            print(f"  {path.relative_to(root)} ({age_days(path)}d)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
