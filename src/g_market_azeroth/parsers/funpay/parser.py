from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag
from pydantic import ValidationError

from g_market_azeroth.parsers.funpay.client import FunPayClient
from g_market_azeroth.parsers.funpay.models import FunPayMarketSnapshot, FunPayOffer


FUNPAY_BASE_URL = "https://funpay.com"
MIN_ORDER_PATTERNS = (
    re.compile(r"minimum(?:\s+order)?[^\d]{0,80}([\d\s.,]+)", re.IGNORECASE),
    re.compile(r"min(?:imum)?\.?\s+order[^\d]{0,80}([\d\s.,]+)", re.IGNORECASE),
    re.compile(
        "\u043c\u0438\u043d\u0438\u043c"
        "(?:\u0443\u043c|\u0430\u043b\u044c\u043d\u044b\u0439"
        "\\s+\u0437\u0430\u043a\u0430\u0437)?[^\\d]{0,80}([\\d\\s.,]+)",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True, slots=True)
class ListingSelectors:
    offer: str = "a.tc-item"
    server_link: str = "a[href*='/chips/']"
    filter_candidate: str = "select, option, [data-server], [data-side], [data-filter], .dropdown-menu"
    server: str = ".tc-server"
    faction: str = ".tc-side"
    seller_name: str = ".media-user-name"
    stock: str = ".tc-amount"
    price: str = ".tc-price"
    description: str = ".tc-desc, .tc-description, .tc-comment"


SELECTORS = ListingSelectors()


@dataclass(frozen=True, slots=True)
class ListingDebugReport:
    offer_rows_count: int
    unique_groups_count: int
    first_groups: tuple[tuple[str | None, str | None], ...]
    server_filter_elements_count: int
    server_links_count: int
    sample_server_links: tuple[str, ...]


def parse_listing_page(html: str, source_type: str) -> list[FunPayOffer]:
    soup = BeautifulSoup(html, "lxml")
    offers: list[FunPayOffer] = []

    for offer_node in soup.select(SELECTORS.offer):
        if not isinstance(offer_node, Tag):
            continue

        try:
            offer = _parse_offer_node(offer_node, source_type)
        except (InvalidOperation, TypeError, ValueError, ValidationError):
            continue

        if offer is not None:
            offers.append(offer)

    return offers


def inspect_listing_page(html: str) -> ListingDebugReport:
    soup = BeautifulSoup(html, "lxml")
    offers = parse_listing_page(html, source_type="debug")
    groups = sorted({(offer.server, offer.faction) for offer in offers})
    server_links = _server_links(soup)

    return ListingDebugReport(
        offer_rows_count=len(soup.select(SELECTORS.offer)),
        unique_groups_count=len(groups),
        first_groups=tuple(groups[:30]),
        server_filter_elements_count=len(soup.select(SELECTORS.filter_candidate)),
        server_links_count=len(server_links),
        sample_server_links=tuple(server_links[:10]),
    )


def parse_offer_detail_page(html: str) -> int | None:
    soup = BeautifulSoup(html, "lxml")
    for line in soup.get_text("\n", strip=True).splitlines():
        min_order_gold = _min_order_from_text(line)
        if min_order_gold is not None:
            return min_order_gold

    return None


class FunPayParser:
    def __init__(self, client: FunPayClient | None = None) -> None:
        self._client = client or FunPayClient()

    def parse_market(self, url: str, *, limit: int | None = None) -> FunPayMarketSnapshot:
        html = self._client.get_text(url)
        offers = parse_listing_page(html, source_type="unknown")
        if limit is not None:
            offers = offers[:limit]

        return FunPayMarketSnapshot(source_url=url, offers=tuple(offers))


def _parse_offer_node(node: Tag, source_type: str) -> FunPayOffer | None:
    offer_url = _get_href(node)
    if offer_url is None:
        return None

    return FunPayOffer(
        source_type=source_type,
        offer_url=offer_url,
        server=_text_or_none(node, SELECTORS.server),
        faction=_text_or_none(node, SELECTORS.faction),
        seller_name=_text_or_none(node, SELECTORS.seller_name),
        price_per_1000=_decimal_or_none(_text_or_none(node, SELECTORS.price)),
        stock_gold=_stock_or_none(node),
        description=_text_or_none(node, SELECTORS.description),
    )


def _get_href(node: Tag) -> str | None:
    href = node.get("href")
    if not isinstance(href, str) or not href.strip():
        return None

    return urljoin(FUNPAY_BASE_URL, href.strip())


def _text_or_none(node: Tag, selector: str) -> str | None:
    found = node.select_one(selector)
    if found is None:
        return None

    value = found.get_text(" ", strip=True)
    return value or None


def _decimal_or_none(value: str | None) -> Decimal | None:
    if value is None:
        return None

    normalized = _first_number(value)
    return Decimal(normalized) if normalized is not None else None


def _stock_or_none(node: Tag) -> int | None:
    stock_node = node.select_one(SELECTORS.stock)
    if stock_node is None:
        return None

    raw_value = stock_node.get("data-s")
    if isinstance(raw_value, str) and raw_value.strip():
        amount_text = raw_value
    else:
        amount_text = stock_node.get_text(" ", strip=True)

    normalized = _first_number(amount_text)
    if normalized is None:
        return None

    amount = Decimal(normalized)
    unit_text = stock_node.get_text(" ", strip=True).lower()
    if "к" in unit_text or "k" in unit_text:
        amount *= 1000

    return int(amount)


def _first_number(value: str) -> str | None:
    cleaned = value.replace("\xa0", " ").replace(",", ".")
    digits: list[str] = []
    seen_digit = False
    seen_dot = False

    for char in cleaned:
        if char.isdigit():
            digits.append(char)
            seen_digit = True
            continue

        if char == "." and seen_digit and not seen_dot:
            digits.append(char)
            seen_dot = True
            continue

        if seen_digit and char not in {" ", "\u202f"}:
            break

    number = "".join(digits).replace(" ", "").replace("\u202f", "")
    return number if number and number != "." else None


def _min_order_from_text(value: str) -> int | None:
    for pattern in MIN_ORDER_PATTERNS:
        match = pattern.search(value)
        if match is None:
            continue

        number = _first_number(match.group(1))
        if number is None:
            continue

        try:
            amount = int(Decimal(number))
        except InvalidOperation:
            continue

        if amount > 0:
            return amount

    return None


def _server_links(soup: BeautifulSoup) -> list[str]:
    links: list[str] = []
    for link in soup.select(SELECTORS.server_link):
        if not isinstance(link, Tag):
            continue

        href = link.get("href")
        text = link.get_text(" ", strip=True)
        if isinstance(href, str) and text and "/chips/offer" not in href:
            links.append(f"{text} -> {urljoin(FUNPAY_BASE_URL, href)}")

    return links
