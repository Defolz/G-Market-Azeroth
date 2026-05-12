"""Parser service foundation for catalog providers."""

from g_market_azeroth.services.parsers.base import CatalogParser, ParsedProduct, ParserError
from g_market_azeroth.services.parsers.funpay import FunPayCatalogParser
from g_market_azeroth.services.parsers.runner import ParserFetchResult, fetch_products_safely

__all__ = [
    "CatalogParser",
    "FunPayCatalogParser",
    "ParsedProduct",
    "ParserError",
    "ParserFetchResult",
    "fetch_products_safely",
]
