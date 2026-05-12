import asyncio
import logging
import sqlite3
from decimal import Decimal

from g_market_azeroth.services.parsers import (
    FunPayCatalogParser,
    ParsedProduct,
    ParserError,
    fetch_products_safely,
)


def create_funpay_source_db(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE funpay_market_best_entry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                server TEXT NOT NULL,
                faction TEXT,
                best_offer_url TEXT,
                seller_name TEXT,
                price_per_1000 REAL NOT NULL,
                min_order_gold INTEGER NULL,
                stock_gold INTEGER,
                parsed_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def insert_funpay_row(
    path,
    *,
    source_type: str = "official",
    server: str = "Soulseeker",
    faction: str | None = "Alliance",
    offer_url: str | None = "https://funpay.com/lots/1/",
    price: float = 120.0,
) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO funpay_market_best_entry (
                source_type,
                server,
                faction,
                best_offer_url,
                seller_name,
                price_per_1000,
                parsed_at,
                created_at
            )
            VALUES (?, ?, ?, ?, 'seller', ?, '2026-01-01', '2026-01-01')
            """,
            (source_type, server, faction, offer_url, price),
        )


def test_funpay_catalog_parser_returns_normalized_products(tmp_path) -> None:
    source_db = tmp_path / "funpay.sqlite3"
    create_funpay_source_db(source_db)
    insert_funpay_row(source_db)

    products = asyncio.run(FunPayCatalogParser(source_db=source_db).fetch_products())

    assert products == [
        ParsedProduct(
            server="Soulseeker",
            faction="Alliance",
            price_per_1000=Decimal("120.0"),
            external_id="https://funpay.com/lots/1/",
            title="official: Soulseeker / Alliance",
        )
    ]


def test_funpay_catalog_parser_logs_parse_errors(tmp_path, caplog) -> None:
    source_db = tmp_path / "funpay.sqlite3"
    create_funpay_source_db(source_db)
    insert_funpay_row(source_db, faction=None)

    with caplog.at_level(logging.WARNING, logger="g_market_azeroth.services.parsers.funpay"):
        products = asyncio.run(FunPayCatalogParser(source_db=source_db).fetch_products())

    assert products == []
    assert "FunPay parser skipped invalid row" in caplog.text


def test_fetch_products_safely_catches_parser_errors(caplog) -> None:
    class BrokenParser:
        async def fetch_products(self) -> list[ParsedProduct]:
            raise ParserError("source unavailable")

    with caplog.at_level(logging.WARNING, logger="g_market_azeroth.services.parsers.runner"):
        result = asyncio.run(fetch_products_safely(BrokenParser()))

    assert result.products == []
    assert result.failed_count == 1
    assert "parser fetch failed" in caplog.text
