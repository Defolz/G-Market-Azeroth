from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from g_market_azeroth.parsers.funpay.client import FunPayClient
from g_market_azeroth.parsers.funpay.export import export_market_tables
from g_market_azeroth.parsers.funpay.models import FunPayOffer
from g_market_azeroth.parsers.funpay.parser import (
    ListingDebugReport,
    inspect_listing_page,
    parse_listing_page,
)
from g_market_azeroth.parsers.funpay.repository import (
    FunPayAuditReport,
    get_audit_report,
    refresh_market_tables,
    save_offers,
)


DEFAULT_OFFICIAL_URL = "https://funpay.com/chips/2/"
DEFAULT_PRIVATE_URL = "https://funpay.com/chips/34/"
DEFAULT_DB_PATH = "data/funpay_prices.sqlite3"
DEFAULT_EXPORT_DIR = "exports"
DEFAULT_DEBUG_DIR = "debug"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse FunPay market prices.")
    parser.add_argument("--official-url", default=DEFAULT_OFFICIAL_URL)
    parser.add_argument("--private-url", default=DEFAULT_PRIVATE_URL)
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--export-dir", default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dump-json", default=None)
    parser.add_argument("--save-db", action="store_true")
    parser.add_argument("--refresh-market", action="store_true")
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--debug-listing", action="store_true")
    parser.add_argument("--include-any-server", action="store_true")
    parser.add_argument("--include-any-faction", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    offers: list[FunPayOffer] = []

    if _should_fetch_pages(args):
        client = FunPayClient()
        official_html = client.get_text(args.official_url)
        private_html = client.get_text(args.private_url)
        official_offers = parse_listing_page(
            official_html,
            source_type="official",
        )
        private_offers = parse_listing_page(
            private_html,
            source_type="private",
        )

        if args.debug_listing:
            _save_debug_html(official_html, private_html)
            _print_debug_listing(
                inspect_listing_page(official_html),
                inspect_listing_page(private_html),
            )

        if args.limit is not None:
            official_offers = official_offers[: args.limit]
            private_offers = private_offers[: args.limit]

        print(f"official offers: {len(official_offers)}")
        print(f"private offers: {len(private_offers)}")

        offers = official_offers + private_offers

    if args.dump_json:
        _dump_json(Path(args.dump_json), offers)

    if args.save_db:
        saved_count = save_offers(Path(args.db_path), offers)
        print(f"saved offers: {saved_count}")

    if args.refresh_market:
        min_price_count, best_entry_count = refresh_market_tables(
            Path(args.db_path),
            exclude_any_server=not args.include_any_server,
            exclude_any_faction=not args.include_any_faction,
        )
        print(f"market min price rows: {min_price_count}")
        print(f"market best entry rows: {best_entry_count}")

    if args.export:
        xlsx_path, min_price_csv_path = export_market_tables(
            Path(args.db_path),
            Path(args.export_dir),
        )
        best_entry_csv_path = Path(args.export_dir) / "funpay_market_best_entry_latest.csv"
        print(f"created xlsx: {xlsx_path}")
        print(f"created csv: {min_price_csv_path}")
        print(f"created csv: {best_entry_csv_path}")

    if args.audit:
        _print_audit_report(get_audit_report(Path(args.db_path)))


def _should_fetch_pages(args: argparse.Namespace) -> bool:
    return bool(args.save_db or args.dump_json or args.debug_listing)


def _dump_json(path: Path, offers: list[FunPayOffer]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [offer.model_dump(mode="json") for offer in offers]
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _print_audit_report(report: FunPayAuditReport) -> None:
    print(f"raw offers count: {report.raw_offers_count}")
    print(f"min_price rows count: {report.min_price_rows_count}")
    print(f"best_entry rows count: {report.best_entry_rows_count}")
    print(f"rows with empty server: {report.empty_server_rows_count}")
    print(f"rows with empty faction: {report.empty_faction_rows_count}")
    print(f"rows with empty price_per_1000: {report.empty_price_rows_count}")
    print(f"raw rows with any server: {report.any_server_rows_count}")
    print(f"raw rows with any faction: {report.any_faction_rows_count}")
    print(f"market rows after filtering: {report.market_rows_after_filtering}")
    print(f"min price_per_1000: {report.min_price_per_1000}")
    print(f"max price_per_1000: {report.max_price_per_1000}")
    print("top groups by offers count:")
    for group in report.top_groups:
        print(
            f"- {group.source_type} | {group.server} | "
            f"{group.faction}: {group.offers_count}"
        )


def _save_debug_html(official_html: str, private_html: str) -> None:
    debug_dir = Path(DEFAULT_DEBUG_DIR)
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "funpay_official.html").write_text(official_html, encoding="utf-8")
    (debug_dir / "funpay_private.html").write_text(private_html, encoding="utf-8")


def _print_debug_listing(
    official_report: ListingDebugReport,
    private_report: ListingDebugReport,
) -> None:
    _print_one_debug_listing("official", official_report)
    _print_one_debug_listing("private", private_report)


def _print_one_debug_listing(source_type: str, report: ListingDebugReport) -> None:
    print(f"{source_type} offer rows found: {report.offer_rows_count}")
    print(f"{source_type} unique server/faction groups: {report.unique_groups_count}")
    print(f"{source_type} first 30 server/faction groups:")
    for server, faction in report.first_groups:
        print(f"- {server} | {faction}")
    print(f"{source_type} filter/category candidate elements: {report.server_filter_elements_count}")
    print(f"{source_type} chips/category links: {report.server_links_count}")
    for link in report.sample_server_links:
        print(f"- {link}")


if __name__ == "__main__":
    main()
