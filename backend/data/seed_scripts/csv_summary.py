"""csv_summary — สรุปไฟล์ CSV: จำนวนแถว/คอลัมน์, ค่าว่าง, ช่วงของคอลัมน์ตัวเลข

ใช้: python csv_summary.py <file> [rows_to_scan]
ค่าเริ่มต้น: rows_to_scan=5000
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: csv_summary.py <file> [rows]")
        return 2
    path = Path(sys.argv[1])
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    if not path.exists():
        print(f"not found: {path}")
        return 2

    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(handle, dialect=dialect)
        columns = reader.fieldnames or []

        rows = 0
        empty = {column: 0 for column in columns}
        numeric: dict[str, tuple[float, float]] = {}
        for row in reader:
            rows += 1
            for column in columns:
                value = (row.get(column) or "").strip()
                if not value:
                    empty[column] += 1
                    continue
                try:
                    number = float(value.replace(",", ""))
                except ValueError:
                    continue
                low, high = numeric.get(column, (number, number))
                numeric[column] = (min(low, number), max(high, number))
            if rows >= limit:
                break

    print(f"file    : {path.resolve()}")
    print(f"delim   : {repr(dialect.delimiter)}")
    print(f"rows    : {rows}{' (capped)' if rows >= limit else ''}")
    print(f"columns : {len(columns)} -> {', '.join(columns)}")
    print("\ncolumn                 empty   numeric range")
    for column in columns:
        bounds = numeric.get(column)
        span = f"{bounds[0]:.4g} … {bounds[1]:.4g}" if bounds else "-"
        print(f"{column[:22]:22} {empty[column]:6}   {span}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
