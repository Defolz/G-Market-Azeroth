from __future__ import annotations

import argparse
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SOURCE_DB_PATH = "data/funpay_prices.sqlite3"
DEFAULT_BOT_DB_PATH = "data/g_market_azeroth.sqlite3"
DEFAULT_MAX_PRODUCTS = 20
SOURCE_TYPE_TO_REALM_TYPE = {
    "official": "off",
    "private": "pirate",
}


@dataclass(slots=True)
class SourceProduct:
    realm_type: str
    server: str
    side: str
    price: str


@dataclass(slots=True)
class SyncSummary:
    dry_run: bool
    source_rows: int
    would_create: int
    would_update: int
    applied_create: int
    applied_update: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync FunPay market rows into bot products.")
    parser.add_argument("--source-db", default=DEFAULT_SOURCE_DB_PATH)
    parser.add_argument("--bot-db", default=os.getenv("DATABASE_PATH", DEFAULT_BOT_DB_PATH))
    parser.add_argument("--max-products", type=int, default=DEFAULT_MAX_PRODUCTS)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = sync_funpay_products(
        source_db=Path(args.source_db),
        bot_db=Path(args.bot_db),
        max_products=args.max_products,
        apply_changes=args.apply,
    )
    _print_summary(summary)


def sync_funpay_products(
    *,
    source_db: Path,
    bot_db: Path,
    max_products: int,
    apply_changes: bool,
) -> SyncSummary:
    if max_products <= 0:
        raise ValueError("--max-products must be positive")

    source_products = _read_source_products(source_db, max_products)
    dry_run = not apply_changes
    would_create = 0
    would_update = 0
    applied_create = 0
    applied_update = 0

    with sqlite3.connect(bot_db) as connection:
        connection.row_factory = sqlite3.Row
        _init_products_schema(connection)

        for product in source_products:
            existing_product_id = _find_product_id(connection, product)
            if existing_product_id is None:
                would_create += 1
                if apply_changes:
                    _create_product(connection, product)
                    applied_create += 1
                continue

            would_update += 1
            if apply_changes:
                _update_product_price(connection, existing_product_id, product.price)
                applied_update += 1

        if apply_changes:
            connection.commit()

    return SyncSummary(
        dry_run=dry_run,
        source_rows=len(source_products),
        would_create=would_create,
        would_update=would_update,
        applied_create=applied_create,
        applied_update=applied_update,
    )


def _read_source_products(source_db: Path, max_products: int) -> list[SourceProduct]:
    with sqlite3.connect(source_db) as connection:
        rows = connection.execute(
            """
            SELECT source_type, server, faction, price_per_1000
            FROM funpay_market_best_entry
            WHERE price_per_1000 IS NOT NULL
            ORDER BY source_type, server COLLATE NOCASE, faction COLLATE NOCASE
            LIMIT ?
            """,
            (max_products,),
        ).fetchall()

    products: list[SourceProduct] = []
    for source_type, server, faction, price_per_1000 in rows:
        realm_type = SOURCE_TYPE_TO_REALM_TYPE.get(str(source_type))
        if realm_type is None:
            continue

        products.append(
            SourceProduct(
                realm_type=realm_type,
                server=str(server),
                side=str(faction),
                price=_format_price(float(price_per_1000)),
            )
        )

    return products


def _init_products_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            realm_type TEXT NOT NULL,
            server TEXT NOT NULL,
            side TEXT NOT NULL,
            price TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_products_catalog
        ON products(realm_type, server, side, is_active)
        """
    )


def _find_product_id(connection: sqlite3.Connection, product: SourceProduct) -> int | None:
    row = connection.execute(
        """
        SELECT id
        FROM products
        WHERE realm_type = ? AND server = ? AND side = ? AND is_active = 1
        ORDER BY id ASC
        LIMIT 1
        """,
        (product.realm_type, product.server, product.side),
    ).fetchone()
    return int(row["id"]) if row else None


def _create_product(connection: sqlite3.Connection, product: SourceProduct) -> None:
    connection.execute(
        """
        INSERT INTO products (realm_type, server, side, price)
        VALUES (?, ?, ?, ?)
        """,
        (product.realm_type, product.server, product.side, product.price),
    )


def _update_product_price(
    connection: sqlite3.Connection,
    product_id: int,
    price: str,
) -> None:
    connection.execute(
        """
        UPDATE products
        SET price = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND is_active = 1
        """,
        (price, product_id),
    )


def _format_price(price: float) -> str:
    return f"{price:.2f}".rstrip("0").rstrip(".")


def _print_summary(summary: SyncSummary) -> None:
    print(f"dry run: {'yes' if summary.dry_run else 'no'}")
    print(f"source rows: {summary.source_rows}")
    print(f"would create: {summary.would_create}")
    print(f"would update: {summary.would_update}")
    print(f"applied create: {summary.applied_create}")
    print(f"applied update: {summary.applied_update}")


if __name__ == "__main__":
    main()
