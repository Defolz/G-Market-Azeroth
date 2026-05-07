"""FunPay parser skeleton."""

from g_market_azeroth.parsers.funpay.client import FunPayClient
from g_market_azeroth.parsers.funpay.models import FunPayMarketSnapshot, FunPayOffer
from g_market_azeroth.parsers.funpay.parser import FunPayParser

__all__ = [
    "FunPayClient",
    "FunPayMarketSnapshot",
    "FunPayOffer",
    "FunPayParser",
]
