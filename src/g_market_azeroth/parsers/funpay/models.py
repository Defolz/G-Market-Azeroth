from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class FunPayOffer(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_type: str
    offer_url: HttpUrl
    parsed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    server: str | None = None
    faction: str | None = None
    seller_name: str | None = None
    price_per_1000: Decimal | None = Field(default=None, ge=0)
    stock_gold: int | None = Field(default=None, ge=0)
    description: str | None = None


class FunPayMarketSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_url: HttpUrl
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    offers: tuple[FunPayOffer, ...] = ()
