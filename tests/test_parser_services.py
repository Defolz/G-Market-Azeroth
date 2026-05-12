import asyncio
import logging
import sqlite3
from decimal import Decimal

from g_market_azeroth.services.parsers import (
    FunPayCatalogParser,
    ParsedProduct,
    ParserError,
    fetch_products_safely,
    preview_catalog_changes,
)
from g_market_azeroth.repositories.products import Product


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
            realm_type="off",
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


def make_product(*, product_id: int, price: str, is_active: bool = True) -> Product:
    return Product(
        id=product_id,
        game_type="off",
        server="Soulseeker",
        faction="Alliance",
        price=price,
        is_active=is_active,
        created_at="2026-01-01",
        updated_at="2026-01-01",
    )


def test_parser_preview_counts_new_updates_and_hidden_products() -> None:
    class PreviewParser:
        async def fetch_products(self) -> list[ParsedProduct]:
            return [
                ParsedProduct(
                    realm_type="off",
                    server="Soulseeker",
                    faction="Alliance",
                    price_per_1000=Decimal("125"),
                    external_id="existing",
                    title="Existing",
                ),
                ParsedProduct(
                    realm_type="pirate",
                    server="Sirus",
                    faction="Horde",
                    price_per_1000=Decimal("90"),
                    external_id="new",
                    title="New",
                ),
                ParsedProduct(
                    realm_type="off",
                    server="Nek'Rosh",
                    faction="Alliance",
                    price_per_1000=Decimal("100"),
                    external_id="hidden",
                    title="Hidden",
                ),
            ]

    current_products = [
        make_product(product_id=1, price="120 ₽"),
        Product(
            id=2,
            game_type="off",
            server="Nek'Rosh",
            faction="Alliance",
            price="100 ₽",
            is_active=False,
            created_at="2026-01-01",
            updated_at="2026-01-01",
        ),
    ]

    summary = asyncio.run(preview_catalog_changes(PreviewParser(), current_products=current_products))

    assert summary.fetched_count == 3
    assert summary.new_count == 1
    assert summary.update_count == 1
    assert summary.hidden_count == 1
    assert summary.error_count == 0
