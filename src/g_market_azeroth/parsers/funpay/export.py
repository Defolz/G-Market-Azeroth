from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet


RAW_OFFERS_QUERY = """
SELECT
    id,
    source_type,
    server,
    faction,
    seller_name,
    offer_url,
    price_per_1000,
    stock_gold,
    min_order_gold,
    description,
    parsed_at,
    created_at,
    batch_id
FROM funpay_offers_raw
ORDER BY id
"""
MIN_PRICE_QUERY = """
SELECT
    source_type,
    server,
    faction,
    best_offer_url,
    seller_name,
    min_price_per_1000,
    min_order_gold,
    stock_gold,
    parsed_at,
    created_at
FROM funpay_market_min_price
ORDER BY source_type, server, faction
"""
BEST_ENTRY_QUERY = """
SELECT
    source_type,
    server,
    faction,
    best_offer_url,
    seller_name,
    price_per_1000,
    min_order_gold,
    stock_gold,
    parsed_at,
    created_at
FROM funpay_market_best_entry
ORDER BY source_type, server, faction
"""


def export_market_tables(db_path: Path, export_dir: Path) -> tuple[Path, Path]:
    export_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = export_dir / "funpay_prices_latest.xlsx"
    min_price_csv_path = export_dir / "funpay_market_min_price_latest.csv"
    best_entry_csv_path = export_dir / "funpay_market_best_entry_latest.csv"

    with sqlite3.connect(db_path) as connection:
        raw_offers = _fetch_rows(connection, RAW_OFFERS_QUERY)
        min_price = _fetch_rows(connection, MIN_PRICE_QUERY)
        best_entry = _fetch_rows(connection, BEST_ENTRY_QUERY)

    _write_xlsx(
        xlsx_path,
        sheets={
            "raw_offers": raw_offers,
            "min_price": min_price,
            "best_entry": best_entry,
        },
    )
    _write_csv(min_price_csv_path, min_price)
    _write_csv(best_entry_csv_path, best_entry)

    return xlsx_path, min_price_csv_path


def _fetch_rows(connection: sqlite3.Connection, query: str) -> list[dict[str, object]]:
    cursor = connection.execute(query)
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _write_xlsx(
    path: Path,
    *,
    sheets: dict[str, list[dict[str, object]]],
) -> None:
    workbook = Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)

    for title, rows in sheets.items():
        worksheet = workbook.create_sheet(title=title)
        _append_rows(worksheet, rows)
        _format_sheet(worksheet)

    workbook.save(path)


def _append_rows(worksheet: Worksheet, rows: list[dict[str, object]]) -> None:
    if not rows:
        return

    headers = list(rows[0].keys())
    worksheet.append(headers)
    for row in rows:
        worksheet.append([row[header] for header in headers])


def _format_sheet(worksheet: Worksheet) -> None:
    worksheet.freeze_panes = "A2"
    for column_cells in worksheet.columns:
        width = max(len(str(cell.value or "")) for cell in column_cells) + 2
        worksheet.column_dimensions[column_cells[0].column_letter].width = min(width, 60)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        if not rows:
            return

        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
