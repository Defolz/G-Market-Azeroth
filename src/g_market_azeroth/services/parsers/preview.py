from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from g_market_azeroth.repositories.products import Product
from g_market_azeroth.services.parsers.base import CatalogParser, ParsedProduct
from g_market_azeroth.services.parsers.runner import fetch_products_safely

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ParserPreviewSummary:
    fetched_count: int
    new_count: int
    update_count: int
    hidden_count: int
    error_count: int


async def preview_catalog_changes(
    parser: CatalogParser,
    *,
    current_products: list[Product],
    logger: logging.Logger = LOGGER,
) -> ParserPreviewSummary:
    logger.info("parser preview started", extra={"event": "parser_preview_started"})
    result = await fetch_products_safely(parser)
    summary = _build_preview_summary(result.products, current_products, result.failed_count)
    logger.info(
        "parser preview finished",
        extra={
            "event": "parser_preview_finished",
            "fetched_count": summary.fetched_count,
            "new_count": summary.new_count,
            "update_count": summary.update_count,
            "hidden_count": summary.hidden_count,
            "error_count": summary.error_count,
        },
    )
    return summary


def _build_preview_summary(
    parsed_products: list[ParsedProduct],
    current_products: list[Product],
    error_count: int,
) -> ParserPreviewSummary:
    current_by_key = {_product_key(product): product for product in current_products}
    new_count = 0
    update_count = 0
    hidden_count = 0

    for parsed_product in parsed_products:
        current_product = current_by_key.get(_parsed_product_key(parsed_product))
        if current_product is None:
            new_count += 1
            continue

        if not current_product.is_active:
            hidden_count += 1
            continue

        current_price = _parse_product_price(current_product.price)
        if current_price is None or current_price != parsed_product.price_per_1000:
            update_count += 1

    return ParserPreviewSummary(
        fetched_count=len(parsed_products),
        new_count=new_count,
        update_count=update_count,
        hidden_count=hidden_count,
        error_count=error_count,
    )


def _product_key(product: Product) -> tuple[str, str, str]:
    return product.realm_type, product.server.casefold().strip(), product.side.casefold().strip()


def _parsed_product_key(product: ParsedProduct) -> tuple[str, str, str]:
    return product.realm_type, product.server.casefold().strip(), product.faction.casefold().strip()


def _parse_product_price(value: str) -> Decimal | None:
    normalized = value.strip().replace(" ", "").replace(",", ".")
    normalized = "".join(character for character in normalized if character.isdigit() or character == ".")
    if not normalized or normalized == ".":
        return None

    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None
