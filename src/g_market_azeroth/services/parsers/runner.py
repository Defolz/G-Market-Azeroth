from __future__ import annotations

import logging
from dataclasses import dataclass

from g_market_azeroth.services.parsers.base import CatalogParser, ParsedProduct, ParserError

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ParserFetchResult:
    products: list[ParsedProduct]
    failed_count: int = 0


async def fetch_products_safely(
    parser: CatalogParser,
    *,
    logger: logging.Logger = LOGGER,
) -> ParserFetchResult:
    logger.info("parser fetch started", extra={"event": "parser_started"})
    try:
        products = await parser.fetch_products()
    except ParserError as exc:
        logger.warning(
            "parser fetch failed",
            extra={"event": "parser_failed", "failed_count": 1, "error": str(exc)},
        )
        return ParserFetchResult(products=[], failed_count=1)
    except Exception as exc:
        logger.warning(
            "parser fetch failed unexpectedly",
            extra={"event": "parser_failed", "failed_count": 1, "error": exc.__class__.__name__},
        )
        return ParserFetchResult(products=[], failed_count=1)

    logger.info(
        "parser fetch completed",
        extra={"event": "parser_completed", "fetched_count": len(products), "failed_count": 0},
    )
    return ParserFetchResult(products=products)
