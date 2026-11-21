"""project_report — สรุปสถานะโปรเจกต์: ไฟล์, LOC, TODO, git status

ใช้: python project_report.py [path]
ค่าเริ่มต้น: path="."
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path

SKIP = {".git", "node_modules", ".venv", "__pycache__", ".svelte-kit", "build", "dist", ".pytest-tmp"}
TEXT_EXT = {
    ".py", ".ts", ".js", ".svelte", ".css", ".html", ".md", ".json", ".yaml", ".yml",
    ".toml", ".txt", ".sql", ".sh", ".ps1",
}
MARKERS = ("TODO", "FIXME", "XXX", "HACK")


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    if not root.exists():
        print(f"not found: {root}")
        return 2

    files = 0
    lines = 0
    by_ext: Counter[str] = Counter()
    markers: list[str] = []

    for path in root.rglob("*"):
        if any(part in SKIP for part in path.parts) or not path.is_file():
            continue
        files += 1
        by_ext[path.suffix.lower() or "(none)"] += 1
        if path.suffix.lower() not in TEXT_EXT:
            continue
        try:
            if path.stat().st_size > 1_048_576:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lines += text.count("\n") + 1
        for number, line in enumerate(text.splitlines(), 1):
            if any(marker in line for marker in MARKERS):
                markers.append(f"{path.relative_to(root)}:{number}")

    print(f"project : {root.resolve()}")
    print(f"files   : {files}")
    print(f"lines   : {lines}")
    print("by ext  : " + ", ".join(f"{ext}={count}" for ext, count in by_ext.most_common(6)))
    print(f"markers : {len(markers)}")
    for entry in markers[:15]:
        print(f"  - {entry}")
    if len(markers) > 15:
        print(f"  … and {len(markers) - 15} more")

    if (root / ".git").exists():
        result = subprocess.run(
            ["git", "status", "--short"], cwd=str(root), capture_output=True, text=True, check=False
        )
        changed = [line for line in result.stdout.splitlines() if line.strip()]
        print(f"git     : {len(changed)} changed")
        for line in changed[:10]:
            print(f"  {line}")
    else:
        print("git     : not a repository")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
