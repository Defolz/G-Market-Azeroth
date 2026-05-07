from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def export_unique_servers(db_path: Path, output_path: Path) -> int:
    rows = _fetch_unique_servers(db_path)
    payload = [
        {
            "source_type": row["source_type"],
            "server": row["server"],
            "faction": row["faction"],
            "normalized_server": None,
            "normalized_faction": None,
            "product_id": None,
        }
        for row in rows
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    for row in rows:
        print(f"{row['source_type']} | {row['server']} | {row['faction']}")

    return len(rows)


def _fetch_unique_servers(db_path: Path) -> list[dict[str, str]]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT source_type, server, faction
            FROM funpay_market_best_entry
            GROUP BY source_type, server, faction
            ORDER BY source_type, server COLLATE NOCASE, faction COLLATE NOCASE
            """
        ).fetchall()

    return [
        {
            "source_type": str(row[0]),
            "server": str(row[1]),
            "faction": str(row[2]) if row[2] is not None else "",
        }
        for row in rows
    ]
