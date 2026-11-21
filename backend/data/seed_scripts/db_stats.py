"""db_stats — สถิติของระบบจาก SQLite โดยตรง

ใช้: python db_stats.py [db_path]
ค่าเริ่มต้น: ../data/outworld.db (เทียบกับ cwd = workspace)
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

TABLES = (
    "projects", "chats", "messages", "knowledge", "providers",
    "commands", "tool_calls", "approvals", "runs", "patterns", "feedback",
)


def main() -> int:
    db = Path(sys.argv[1] if len(sys.argv) > 1 else "../data/outworld.db")
    if not db.exists():
        print(f"not found: {db.resolve()}")
        return 2

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        print(f"db      : {db.resolve()}")
        print(f"size    : {db.stat().st_size / 1024:.0f} KB")
        print(f"schema  : v{conn.execute('PRAGMA user_version').fetchone()[0]}")
        print("\nrows")
        for table in TABLES:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.Error:
                continue
            print(f"  {table:12} {count}")

        print("\nrecent runs")
        for row in conn.execute(
            "SELECT intent, intent_source, status, tool_count, started_at"
            " FROM runs ORDER BY started_at DESC LIMIT 5"
        ):
            print(
                f"  {row['started_at'][:16]}  {row['intent_source']:5}"
                f"  {row['status']:6}  tools={row['tool_count']}  {row['intent'][:40]}"
            )

        print("\ntop patterns")
        for row in conn.execute(
            "SELECT name, uses, success FROM patterns ORDER BY success DESC, uses DESC LIMIT 5"
        ):
            print(f"  {row['success']}/{max(row['uses'], 1)}  {row['name'][:60]}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
