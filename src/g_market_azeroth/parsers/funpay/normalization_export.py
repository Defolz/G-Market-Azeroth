from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path


DOMAIN_PATTERN = re.compile(r"\b[\w.-]+\.(?:com|gg|net|org|ru|su|io)\b", re.IGNORECASE)
PROVIDER_PREFIX_PATTERN = re.compile(r"^(?:warmane|stormforge)\b", re.IGNORECASE)
PRICE_NOTE_PATTERN = re.compile(r"\(\s*цена\s+за\s+1\s+золотой\s*\)", re.IGNORECASE)
SPACES_PATTERN = re.compile(r"\s+")

FACTION_ALIASES = {
    "alliance": "alliance",
    "horde": "horde",
    "альянс": "alliance",
    "орда": "horde",
}


def export_normalization_preview(db_path: Path, output_path: Path) -> int:
    rows = _fetch_market_rows(db_path)
    payload = [
        {
            "source_type": row["source_type"],
            "server": row["server"],
            "faction": row["faction"],
            "normalized_server": normalize_server(row["server"]),
            "normalized_faction": normalize_faction(row["faction"]),
        }
        for row in rows
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(rows)


def normalize_server(server: str | None) -> str | None:
    normalized = _normalize_text(server)
    if normalized is None:
        return None

    normalized = DOMAIN_PATTERN.sub(" ", normalized)
    normalized = PROVIDER_PREFIX_PATTERN.sub(" ", normalized)
    normalized = PRICE_NOTE_PATTERN.sub(" ", normalized)
    normalized = normalized.replace("(", " ").replace(")", " ")
    normalized = _collapse_spaces(normalized)
    return normalized or None


def normalize_faction(faction: str | None) -> str | None:
    normalized = _normalize_text(faction)
    if normalized is None:
        return None

    return FACTION_ALIASES.get(normalized, normalized)


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = _collapse_spaces(value.lower().strip())
    return normalized or None


def _collapse_spaces(value: str) -> str:
    return SPACES_PATTERN.sub(" ", value).strip()


def _fetch_market_rows(db_path: Path) -> list[dict[str, str]]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT source_type, server, faction
            FROM funpay_market_best_entry
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
