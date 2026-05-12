from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from g_market_azeroth.database import MarketRepository
from g_market_azeroth.repositories.products import Product
from g_market_azeroth.services.parsers.base import CatalogParser, ParsedProduct
from g_market_azeroth.services.parsers.preview import _parse_product_price, _parsed_product_key, _product_key
from g_market_azeroth.services.parsers.runner import fetch_products_safely

LOGGER = logging.getLogger(__name__)
MAX_APPLY_PRODUCTS = 10_000


@dataclass(frozen=True, slots=True)
class ParserApplySummary:
    created_count: int
    updated_count: int
    hidden_count: int
    error_count: int


async def apply_catalog_changes(
    parser: CatalogParser,
    *,
    database: MarketRepository,
    logger: logging.Logger = LOGGER,
) -> ParserApplySummary:
    logger.info("parser apply started", extra={"event": "parser_apply_started"})
    result = await fetch_products_safely(parser)
    if result.failed_count and not result.products:
        logger.warning(
            "parser apply stopped after parser failure",
            extra={"event": "parser_apply_failed", "failures": result.failed_count},
        )
        return ParserApplySummary(
            created_count=0,
            updated_count=0,
            hidden_count=0,
            error_count=result.failed_count,
        )

    current_products = await database.latest_products(limit=MAX_APPLY_PRODUCTS)
    summary = await _apply_products(
        result.products,
        current_products=current_products,
        database=database,
        error_count=result.failed_count,
        logger=logger,
    )
    logger.info(
        "parser apply finished",
        extra={
            "event": "parser_apply_finished",
            "created_count": summary.created_count,
            "updated_count": summary.updated_count,
            "hidden_count": summary.hidden_count,
            "failures": summary.error_count,
        },
    )
    return summary


async def _apply_products(
    parsed_products: list[ParsedProduct],
    *,
    current_products: list[Product],
    database: MarketRepository,
    error_count: int,
    logger: logging.Logger,
) -> ParserApplySummary:
    current_by_key = {_product_key(product): product for product in current_products}
    active_keys = {_product_key(product) for product in current_products if product.is_active}
    parsed_by_key: dict[tuple[str, str, str], ParsedProduct] = {}

    for parsed_product in parsed_products:
        key = _parsed_product_key(parsed_product)
        if key in parsed_by_key:
            error_count += 1
            logger.warning(
                "parser apply skipped duplicate product",
                extra={"event": "parser_apply_duplicate", "failures": error_count},
            )
            continue
        parsed_by_key[key] = parsed_product

    created_count = 0
    updated_count = 0
    hidden_count = 0

    for key, parsed_product in parsed_by_key.items():
        current_product = current_by_key.get(key)
        if current_product is None:
            await database.create_catalog_product(
                realm_type=parsed_product.realm_type,
                server=parsed_product.server,
                side=parsed_product.faction,
                price=_format_price(parsed_product.price_per_1000),
            )
            created_count += 1
            continue

        if not current_product.is_active:
            continue

        current_price = _parse_product_price(current_product.price)
        if current_price is None or current_price != parsed_product.price_per_1000:
            product = await database.change_product_price(
                product_id=current_product.id,
                price=_format_price(parsed_product.price_per_1000),
            )
            if product is None:
                error_count += 1
                continue
            updated_count += 1

    missing_active_keys = active_keys - set(parsed_by_key)
    for key in missing_active_keys:
        product = current_by_key[key]
        hidden_product = await database.set_product_active(product_id=product.id, is_active=False)
        if hidden_product is None:
            error_count += 1
            continue
        hidden_count += 1

    return ParserApplySummary(
        created_count=created_count,
        updated_count=updated_count,
        hidden_count=hidden_count,
        error_count=error_count,
    )


def _format_price(price: Decimal) -> str:
    normalized = price.normalize()
    text = format(normalized, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text
