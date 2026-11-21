"""tree — โครงสร้างโฟลเดอร์พร้อมขนาดไฟล์

ใช้: python tree.py [path] [max_depth]
ค่าเริ่มต้น: path="." max_depth=3
"""

from __future__ import annotations

import sys
from pathlib import Path

SKIP = {".git", "node_modules", ".venv", "__pycache__", ".svelte-kit", "build", "dist"}


def human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024
    return f"{value:.1f}GB"


def walk(path: Path, depth: int, max_depth: int, prefix: str = "") -> int:
    if depth > max_depth:
        return 0
    try:
        entries = sorted(
            (entry for entry in path.iterdir() if entry.name not in SKIP),
            key=lambda entry: (entry.is_file(), entry.name.lower()),
        )
    except OSError:
        return 0

    total = 0
    for index, entry in enumerate(entries):
        last = index == len(entries) - 1
        branch = "└─ " if last else "├─ "
        if entry.is_dir():
            print(f"{prefix}{branch}{entry.name}/")
            total += walk(entry, depth + 1, max_depth, prefix + ("   " if last else "│  "))
        else:
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            total += size
            print(f"{prefix}{branch}{entry.name} ({human(size)})")
    return total


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    max_depth = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    if not root.exists():
        print(f"not found: {root}")
        return 2
    print(f"{root.resolve()}  (depth<= {max_depth})")
    total = walk(root, 1, max_depth)
    print(f"\ntotal: {human(total)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
