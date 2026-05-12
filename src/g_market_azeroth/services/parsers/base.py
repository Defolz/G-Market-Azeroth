from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ParsedProduct:
    server: str
    faction: str
    price_per_1000: Decimal
    external_id: str
    title: str


class ParserError(RuntimeError):
    """Raised when a parser provider cannot return a clean product list."""


class CatalogParser(Protocol):
    async def fetch_products(self) -> list[ParsedProduct]:
        """Return normalized catalog products from a provider."""
