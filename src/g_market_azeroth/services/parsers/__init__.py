"""Parser service foundation for catalog providers."""

from g_market_azeroth.services.parsers.apply import ParserApplySummary, apply_catalog_changes
from g_market_azeroth.services.parsers.base import CatalogParser, ParsedProduct, ParserError
from g_market_azeroth.services.parsers.funpay import FunPayCatalogParser
from g_market_azeroth.services.parsers.preview import ParserPreviewSummary, preview_catalog_changes
from g_market_azeroth.services.parsers.runner import ParserFetchResult, fetch_products_safely

__all__ = [
    "CatalogParser",
    "FunPayCatalogParser",
    "ParserApplySummary",
    "ParsedProduct",
    "ParserError",
    "ParserFetchResult",
    "ParserPreviewSummary",
    "apply_catalog_changes",
    "fetch_products_safely",
    "preview_catalog_changes",
]
