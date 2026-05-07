from __future__ import annotations

import argparse
import json
import sys
import time
from uuid import uuid4
from pathlib import Path

import httpx


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from g_market_azeroth.parsers.funpay.client import FunPayClient
from g_market_azeroth.parsers.funpay.export import export_market_tables
from g_market_azeroth.parsers.funpay.mapping_export import export_unique_servers
from g_market_azeroth.parsers.funpay.models import FunPayOffer
from g_market_azeroth.parsers.funpay.parser import (
    ListingDebugReport,
    inspect_listing_page,
    parse_offer_detail_page,
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
DEFAULT_UNIQUE_SERVERS_FILENAME = "funpay_unique_servers.json"


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
    parser.add_argument("--fetch-offer-details", action="store_true")
    parser.add_argument("--detail-delay-seconds", type=float, default=1.0)
    parser.add_argument("--max-detail-offers", type=int, default=None)
    parser.add_argument("--detail-progress-every", type=int, default=50)
    parser.add_argument("--export-unique-servers", nargs="?", const="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    batch_id = str(uuid4())
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
        if args.fetch_offer_details:
            if args.limit is None and args.max_detail_offers is None:
                print("warning: fetching details for all offers may take a long time")
            offers = _fetch_offer_details(
                client,
                offers,
                delay_seconds=args.detail_delay_seconds,
                max_detail_offers=args.max_detail_offers,
                progress_every=args.detail_progress_every,
            )

    if args.dump_json:
        _dump_json(Path(args.dump_json), offers)

    if args.save_db:
        saved_count = save_offers(Path(args.db_path), offers, batch_id=batch_id)
        print(f"saved offers: {saved_count}")

    if args.refresh_market:
        min_price_count, best_entry_count = refresh_market_tables(Path(args.db_path))
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

    if args.export_unique_servers is not None:
        export_path = _unique_servers_export_path(args.export_unique_servers)
        rows_count = export_unique_servers(Path(args.db_path), export_path)
        print(f"unique servers exported: {rows_count} to {export_path}")


def _should_fetch_pages(args: argparse.Namespace) -> bool:
    return bool(
        args.save_db
        or args.dump_json
        or args.debug_listing
        or args.fetch_offer_details
    )


def _fetch_offer_details(
    client: FunPayClient,
    offers: list[FunPayOffer],
    *,
    delay_seconds: float,
    max_detail_offers: int | None,
    progress_every: int,
) -> list[FunPayOffer]:
    detail_offers = offers[:max_detail_offers] if max_detail_offers is not None else offers
    enriched_offers: list[FunPayOffer] = list(offers)
    found_count = 0

    for index, offer in enumerate(detail_offers):
        min_order_gold = _fetch_min_order_gold(client, str(offer.offer_url))
        if min_order_gold is not None:
            found_count += 1
            enriched_offers[index] = offer.model_copy(update={"min_order_gold": min_order_gold})

        completed_count = index + 1
        if _should_print_detail_progress(completed_count, len(detail_offers), progress_every):
            print(f"offer details progress: {completed_count}/{len(detail_offers)}")

        if index < len(detail_offers) - 1 and delay_seconds > 0:
            time.sleep(delay_seconds)

    print(f"offer details fetched: {len(detail_offers)}")
    print(f"offers with min_order_gold: {found_count}")
    return enriched_offers


def _should_print_detail_progress(
    completed_count: int,
    total_count: int,
    progress_every: int,
) -> bool:
    if total_count == 0:
        return False

    if completed_count == total_count:
        return True

    return progress_every > 0 and completed_count % progress_every == 0


def _fetch_min_order_gold(client: FunPayClient, offer_url: str) -> int | None:
    try:
        return parse_offer_detail_page(client.get_text(offer_url))
    except (httpx.HTTPError, ValueError):
        return None


def _dump_json(path: Path, offers: list[FunPayOffer]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [offer.model_dump(mode="json") for offer in offers]
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _unique_servers_export_path(raw_path: str) -> Path:
    if not raw_path:
        return Path(DEFAULT_EXPORT_DIR) / DEFAULT_UNIQUE_SERVERS_FILENAME

    path = Path(raw_path)
    if path.suffix:
        return path

    return path / DEFAULT_UNIQUE_SERVERS_FILENAME


def _print_audit_report(report: FunPayAuditReport) -> None:
    print(f"raw offers count: {report.raw_offers_count}")
    print(f"min_price rows count: {report.min_price_rows_count}")
    print(f"best_entry rows count: {report.best_entry_rows_count}")
    print(f"rows with empty server: {report.empty_server_rows_count}")
    print(f"rows with empty faction: {report.empty_faction_rows_count}")
    print(f"rows with empty price_per_1000: {report.empty_price_rows_count}")
    print(f"raw rows with any server: {report.any_server_rows_count}")
    print(f"raw rows with any faction: {report.any_faction_rows_count}")
    print(
        "ignored any server/faction rows in market tables: "
        f"{report.ignored_any_market_rows_count}"
    )
    print(f"rows with min_order_gold: {report.rows_with_min_order_gold_count}")
    print(f"rows without min_order_gold: {report.rows_without_min_order_gold_count}")
    print(f"market rows after filtering: {report.market_rows_after_filtering}")
    print(f"min price_per_1000: {report.min_price_per_1000}")
    print(f"max price_per_1000: {report.max_price_per_1000}")
    print("top groups by offers count:")
    for group in report.top_groups:
        print(
            f"- {group.source_type} | {group.server} | "
            f"{group.faction}: {group.offers_count}"
        )
    print("latest batch:")
    print(f"latest batch id: {report.latest_batch.batch_id}")
    print(f"latest batch created_at: {report.latest_batch.created_at}")
    print(f"latest batch raw offers count: {report.latest_batch.raw_offers_count}")
    print(
        "latest batch rows with min_order_gold: "
        f"{report.latest_batch.rows_with_min_order_gold_count}"
    )
    print(
        "latest batch rows without min_order_gold: "
        f"{report.latest_batch.rows_without_min_order_gold_count}"
    )
    print(
        "latest batch rows with empty server: "
        f"{report.latest_batch.empty_server_rows_count}"
    )
    print(
        "latest batch rows with empty faction: "
        f"{report.latest_batch.empty_faction_rows_count}"
    )
    print(
        "latest batch rows with empty price_per_1000: "
        f"{report.latest_batch.empty_price_rows_count}"
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
