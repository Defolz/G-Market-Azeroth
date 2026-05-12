from __future__ import annotations

import asyncio
import logging
import sqlite3
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from g_market_azeroth.services.parsers.base import ParsedProduct, ParserError

LOGGER = logging.getLogger(__name__)
SOURCE_TYPE_TO_REALM_TYPE = {
    "official": "off",
    "private": "pirate",
}


@dataclass(frozen=True, slots=True)
class FunPayCatalogParser:
    source_db: Path
    max_products: int = 100
    logger: logging.Logger = LOGGER

    async def fetch_products(self) -> list[ParsedProduct]:
        if self.max_products <= 0:
            raise ParserError("max_products must be positive")

        return await asyncio.to_thread(self._fetch_products_sync)

    def _fetch_products_sync(self) -> list[ParsedProduct]:
        self.logger.info("FunPay parser started", extra={"event": "parser_started", "provider": "funpay"})
        failed_count = 0
        products: list[ParsedProduct] = []

        try:
            rows = self._read_best_entry_rows()
        except sqlite3.Error as exc:
            raise ParserError(f"failed to read FunPay source database: {exc.__class__.__name__}") from exc

        for row in rows:
            try:
                products.append(_row_to_product(row))
            except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                failed_count += 1
                self.logger.warning(
                    "FunPay parser skipped invalid row",
                    extra={
                        "event": "parser_parse_error",
                        "provider": "funpay",
                        "failed_count": failed_count,
                        "error": exc.__class__.__name__,
                    },
                )

        self.logger.info(
            "FunPay parser completed",
            extra={
                "event": "parser_completed",
                "provider": "funpay",
                "fetched_count": len(products),
                "failed_count": failed_count,
            },
        )
        return products

    def _read_best_entry_rows(self) -> list[sqlite3.Row]:
        with sqlite3.connect(self.source_db) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(
                """
                SELECT id, source_type, server, faction, best_offer_url, price_per_1000
                FROM funpay_market_best_entry
                WHERE price_per_1000 IS NOT NULL
                ORDER BY source_type, server COLLATE NOCASE, faction COLLATE NOCASE
                LIMIT ?
                """,
                (self.max_products,),
            ).fetchall()


def _row_to_product(row: sqlite3.Row) -> ParsedProduct:
    server = _required_text(row["server"], "server")
    faction = _required_text(row["faction"], "faction")
    price_per_1000 = Decimal(str(row["price_per_1000"]))
    if price_per_1000 <= 0:
        raise ValueError("price_per_1000 must be positive")

    external_id = _external_id(row)
    source_type = _required_text(row["source_type"], "source_type")
    realm_type = SOURCE_TYPE_TO_REALM_TYPE.get(source_type)
    if realm_type is None:
        raise ValueError("source_type is not supported")

    return ParsedProduct(
        realm_type=realm_type,
        server=server,
        faction=faction,
        price_per_1000=price_per_1000,
        external_id=external_id,
        title=f"{source_type}: {server} / {faction}",
    )


def _external_id(row: sqlite3.Row) -> str:
    offer_url = str(row["best_offer_url"] or "").strip()
    if offer_url:
        return offer_url

    source_type = _required_text(row["source_type"], "source_type")
    row_id = int(row["id"])
    return f"funpay:{source_type}:{row_id}"


def _required_text(value: object, field_name: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError(f"{field_name} is required")

    return cleaned
