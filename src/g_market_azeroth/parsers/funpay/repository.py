from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from g_market_azeroth.parsers.funpay.models import FunPayOffer


RAW_OFFERS_TABLE = "funpay_offers_raw"
MIN_PRICE_TABLE = "funpay_market_min_price"
BEST_ENTRY_TABLE = "funpay_market_best_entry"
ANY_SERVER_VALUES = ("Любой", "Any")
ANY_FACTION_VALUES = ("Любая", "Any")


@dataclass(frozen=True, slots=True)
class FunPayGroupCount:
    source_type: str
    server: str | None
    faction: str | None
    offers_count: int


@dataclass(frozen=True, slots=True)
class FunPayAuditReport:
    raw_offers_count: int
    min_price_rows_count: int
    best_entry_rows_count: int
    empty_server_rows_count: int
    empty_faction_rows_count: int
    empty_price_rows_count: int
    any_server_rows_count: int
    any_faction_rows_count: int
    ignored_any_market_rows_count: int
    rows_with_min_order_gold_count: int
    rows_without_min_order_gold_count: int
    market_rows_after_filtering: int
    top_groups: tuple[FunPayGroupCount, ...]
    min_price_per_1000: float | None
    max_price_per_1000: float | None
    latest_batch: FunPayLatestBatchAudit


@dataclass(frozen=True, slots=True)
class FunPayLatestBatchAudit:
    created_at: str | None
    raw_offers_count: int
    rows_with_min_order_gold_count: int
    rows_without_min_order_gold_count: int
    empty_server_rows_count: int
    empty_faction_rows_count: int
    empty_price_rows_count: int


def save_offers(db_path: Path, offers: list[FunPayOffer]) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(UTC).isoformat()

    with sqlite3.connect(db_path) as connection:
        _init_schema(connection)
        connection.executemany(
            """
            INSERT INTO funpay_offers_raw (
                source_type,
                server,
                faction,
                seller_name,
                offer_url,
                price_per_1000,
                stock_gold,
                min_order_gold,
                description,
                parsed_at,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [_offer_to_row(offer, created_at) for offer in offers],
        )

    return len(offers)


def refresh_market_tables(
    db_path: Path,
    *,
    exclude_any_server: bool = True,
    exclude_any_faction: bool = True,
) -> tuple[int, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(UTC).isoformat()

    with sqlite3.connect(db_path) as connection:
        _init_schema(connection)
        latest_raw_created_at = _latest_raw_created_at(connection)
        connection.execute(f"DELETE FROM {MIN_PRICE_TABLE}")
        connection.execute(f"DELETE FROM {BEST_ENTRY_TABLE}")

        if latest_raw_created_at is None:
            return (0, 0)

        filter_sql, filter_params = _market_filter_sql(
            exclude_any_server=exclude_any_server,
            exclude_any_faction=exclude_any_faction,
        )
        _refresh_min_price_table(
            connection,
            latest_raw_created_at,
            created_at,
            filter_sql,
            filter_params,
        )
        _refresh_best_entry_table(
            connection,
            latest_raw_created_at,
            created_at,
            filter_sql,
            filter_params,
        )

        min_price_count = _table_count(connection, MIN_PRICE_TABLE)
        best_entry_count = _table_count(connection, BEST_ENTRY_TABLE)

    return (min_price_count, best_entry_count)


def get_audit_report(db_path: Path) -> FunPayAuditReport:
    with sqlite3.connect(db_path) as connection:
        latest_raw_created_at = _latest_raw_created_at(connection)
        return FunPayAuditReport(
            raw_offers_count=_safe_table_count(connection, RAW_OFFERS_TABLE),
            min_price_rows_count=_safe_table_count(connection, MIN_PRICE_TABLE),
            best_entry_rows_count=_safe_table_count(connection, BEST_ENTRY_TABLE),
            empty_server_rows_count=_raw_empty_count(connection, "server"),
            empty_faction_rows_count=_raw_empty_count(connection, "faction"),
            empty_price_rows_count=_raw_empty_count(connection, "price_per_1000"),
            any_server_rows_count=_raw_any_count(connection, "server", ANY_SERVER_VALUES),
            any_faction_rows_count=_raw_any_count(connection, "faction", ANY_FACTION_VALUES),
            ignored_any_market_rows_count=_latest_ignored_any_count(
                connection,
                latest_raw_created_at,
            ),
            rows_with_min_order_gold_count=_raw_present_count(connection, "min_order_gold"),
            rows_without_min_order_gold_count=_raw_missing_count(connection, "min_order_gold"),
            market_rows_after_filtering=_safe_table_count(connection, MIN_PRICE_TABLE),
            top_groups=_top_group_counts(connection),
            min_price_per_1000=_raw_price_bound(connection, "MIN"),
            max_price_per_1000=_raw_price_bound(connection, "MAX"),
            latest_batch=_latest_batch_audit(connection, latest_raw_created_at),
        )


def _refresh_min_price_table(
    connection: sqlite3.Connection,
    raw_created_at: str,
    created_at: str,
    filter_sql: str,
    filter_params: tuple[str, ...],
) -> None:
    connection.execute(
        f"""
        INSERT INTO {MIN_PRICE_TABLE} (
            source_type,
            server,
            faction,
            best_offer_url,
            seller_name,
            min_price_per_1000,
            min_order_gold,
            stock_gold,
            parsed_at,
            created_at
        )
        SELECT
            source_type,
            server,
            faction,
            offer_url,
            seller_name,
            price_per_1000,
            min_order_gold,
            stock_gold,
            parsed_at,
            ?
        FROM (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY source_type, server, faction
                    ORDER BY price_per_1000 ASC, id ASC
                ) AS rank
            FROM {RAW_OFFERS_TABLE}
            WHERE created_at = ?
              AND server IS NOT NULL
              AND price_per_1000 IS NOT NULL
              {filter_sql}
        )
        WHERE rank = 1
        """,
        (created_at, raw_created_at, *filter_params),
    )


def _refresh_best_entry_table(
    connection: sqlite3.Connection,
    raw_created_at: str,
    created_at: str,
    filter_sql: str,
    filter_params: tuple[str, ...],
) -> None:
    connection.execute(
        f"""
        INSERT INTO {BEST_ENTRY_TABLE} (
            source_type,
            server,
            faction,
            best_offer_url,
            seller_name,
            price_per_1000,
            min_order_gold,
            stock_gold,
            parsed_at,
            created_at
        )
        SELECT
            source_type,
            server,
            faction,
            offer_url,
            seller_name,
            price_per_1000,
            min_order_gold,
            stock_gold,
            parsed_at,
            ?
        FROM (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY source_type, server, faction
                    ORDER BY
                        min_order_gold IS NULL ASC,
                        min_order_gold ASC,
                        price_per_1000 ASC,
                        stock_gold IS NULL ASC,
                        stock_gold DESC,
                        id ASC
                ) AS rank
            FROM {RAW_OFFERS_TABLE}
            WHERE created_at = ?
              AND server IS NOT NULL
              AND price_per_1000 IS NOT NULL
              {filter_sql}
        )
        WHERE rank = 1
        """,
        (created_at, raw_created_at, *filter_params),
    )


def _market_filter_sql(
    *,
    exclude_any_server: bool,
    exclude_any_faction: bool,
) -> tuple[str, tuple[str, ...]]:
    clauses: list[str] = []
    params: list[str] = []
    if exclude_any_server:
        clauses.append(_not_in_clause("server", len(ANY_SERVER_VALUES)))
        params.extend(ANY_SERVER_VALUES)
    if exclude_any_faction:
        clauses.append(_not_in_clause("faction", len(ANY_FACTION_VALUES)))
        params.extend(ANY_FACTION_VALUES)

    return ("".join(clauses), tuple(params))


def _not_in_clause(column_name: str, values_count: int) -> str:
    placeholders = ", ".join("?" for _ in range(values_count))
    return f" AND ({column_name} IS NULL OR {column_name} NOT IN ({placeholders}))"


def _init_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS funpay_offers_raw (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            server TEXT,
            faction TEXT,
            seller_name TEXT,
            offer_url TEXT,
            price_per_1000 REAL,
            stock_gold INTEGER,
            min_order_gold INTEGER NULL,
            description TEXT,
            parsed_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS funpay_market_min_price (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            server TEXT NOT NULL,
            faction TEXT,
            best_offer_url TEXT,
            seller_name TEXT,
            min_price_per_1000 REAL NOT NULL,
            min_order_gold INTEGER NULL,
            stock_gold INTEGER,
            parsed_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS funpay_market_best_entry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            server TEXT NOT NULL,
            faction TEXT,
            best_offer_url TEXT,
            seller_name TEXT,
            price_per_1000 REAL NOT NULL,
            min_order_gold INTEGER NULL,
            stock_gold INTEGER,
            parsed_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _offer_to_row(offer: FunPayOffer, created_at: str) -> tuple[object, ...]:
    price_per_1000 = float(offer.price_per_1000) if offer.price_per_1000 is not None else None

    return (
        offer.source_type,
        offer.server,
        offer.faction,
        offer.seller_name,
        str(offer.offer_url),
        price_per_1000,
        offer.stock_gold,
        offer.min_order_gold,
        offer.description,
        offer.parsed_at.isoformat(),
        created_at,
    )


def _latest_raw_created_at(connection: sqlite3.Connection) -> str | None:
    row = connection.execute(
        """
        SELECT MAX(created_at)
        FROM funpay_offers_raw
        """
    ).fetchone()
    return str(row[0]) if row and row[0] is not None else None


def _table_count(connection: sqlite3.Connection, table_name: str) -> int:
    row = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    return int(row[0])


def _safe_table_count(connection: sqlite3.Connection, table_name: str) -> int:
    if not _table_exists(connection, table_name):
        return 0

    return _table_count(connection, table_name)


def _raw_empty_count(connection: sqlite3.Connection, column_name: str) -> int:
    if not _table_exists(connection, RAW_OFFERS_TABLE):
        return 0

    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM {RAW_OFFERS_TABLE}
        WHERE {column_name} IS NULL OR TRIM(CAST({column_name} AS TEXT)) = ''
        """
    ).fetchone()
    return int(row[0])


def _raw_any_count(
    connection: sqlite3.Connection,
    column_name: str,
    values: tuple[str, ...],
) -> int:
    if not _table_exists(connection, RAW_OFFERS_TABLE):
        return 0

    placeholders = ", ".join("?" for _ in values)
    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM {RAW_OFFERS_TABLE}
        WHERE {column_name} IN ({placeholders})
        """,
        values,
    ).fetchone()
    return int(row[0])


def _latest_ignored_any_count(
    connection: sqlite3.Connection,
    created_at: str | None,
) -> int:
    if created_at is None or not _table_exists(connection, RAW_OFFERS_TABLE):
        return 0

    server_placeholders = ", ".join("?" for _ in ANY_SERVER_VALUES)
    faction_placeholders = ", ".join("?" for _ in ANY_FACTION_VALUES)
    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM {RAW_OFFERS_TABLE}
        WHERE created_at = ?
          AND (
              server IN ({server_placeholders})
              OR faction IN ({faction_placeholders})
          )
        """,
        (created_at, *ANY_SERVER_VALUES, *ANY_FACTION_VALUES),
    ).fetchone()
    return int(row[0])


def _raw_present_count(connection: sqlite3.Connection, column_name: str) -> int:
    if not _table_exists(connection, RAW_OFFERS_TABLE):
        return 0

    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM {RAW_OFFERS_TABLE}
        WHERE {column_name} IS NOT NULL
        """
    ).fetchone()
    return int(row[0])


def _raw_missing_count(connection: sqlite3.Connection, column_name: str) -> int:
    if not _table_exists(connection, RAW_OFFERS_TABLE):
        return 0

    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM {RAW_OFFERS_TABLE}
        WHERE {column_name} IS NULL
        """
    ).fetchone()
    return int(row[0])


def _latest_batch_audit(
    connection: sqlite3.Connection,
    created_at: str | None,
) -> FunPayLatestBatchAudit:
    if created_at is None or not _table_exists(connection, RAW_OFFERS_TABLE):
        return FunPayLatestBatchAudit(
            created_at=None,
            raw_offers_count=0,
            rows_with_min_order_gold_count=0,
            rows_without_min_order_gold_count=0,
            empty_server_rows_count=0,
            empty_faction_rows_count=0,
            empty_price_rows_count=0,
        )

    return FunPayLatestBatchAudit(
        created_at=created_at,
        raw_offers_count=_raw_batch_count(connection, created_at),
        rows_with_min_order_gold_count=_raw_batch_present_count(
            connection,
            "min_order_gold",
            created_at,
        ),
        rows_without_min_order_gold_count=_raw_batch_missing_count(
            connection,
            "min_order_gold",
            created_at,
        ),
        empty_server_rows_count=_raw_batch_empty_count(connection, "server", created_at),
        empty_faction_rows_count=_raw_batch_empty_count(connection, "faction", created_at),
        empty_price_rows_count=_raw_batch_empty_count(
            connection,
            "price_per_1000",
            created_at,
        ),
    )


def _raw_batch_count(connection: sqlite3.Connection, created_at: str) -> int:
    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM {RAW_OFFERS_TABLE}
        WHERE created_at = ?
        """,
        (created_at,),
    ).fetchone()
    return int(row[0])


def _raw_batch_present_count(
    connection: sqlite3.Connection,
    column_name: str,
    created_at: str,
) -> int:
    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM {RAW_OFFERS_TABLE}
        WHERE created_at = ? AND {column_name} IS NOT NULL
        """,
        (created_at,),
    ).fetchone()
    return int(row[0])


def _raw_batch_missing_count(
    connection: sqlite3.Connection,
    column_name: str,
    created_at: str,
) -> int:
    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM {RAW_OFFERS_TABLE}
        WHERE created_at = ? AND {column_name} IS NULL
        """,
        (created_at,),
    ).fetchone()
    return int(row[0])


def _raw_batch_empty_count(
    connection: sqlite3.Connection,
    column_name: str,
    created_at: str,
) -> int:
    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM {RAW_OFFERS_TABLE}
        WHERE created_at = ?
          AND ({column_name} IS NULL OR TRIM(CAST({column_name} AS TEXT)) = '')
        """,
        (created_at,),
    ).fetchone()
    return int(row[0])


def _top_group_counts(connection: sqlite3.Connection) -> tuple[FunPayGroupCount, ...]:
    if not _table_exists(connection, RAW_OFFERS_TABLE):
        return ()

    rows = connection.execute(
        f"""
        SELECT source_type, server, faction, COUNT(*) AS offers_count
        FROM {RAW_OFFERS_TABLE}
        GROUP BY source_type, server, faction
        ORDER BY offers_count DESC, source_type, server, faction
        LIMIT 10
        """
    ).fetchall()
    return tuple(
        FunPayGroupCount(
            source_type=str(row[0]),
            server=str(row[1]) if row[1] is not None else None,
            faction=str(row[2]) if row[2] is not None else None,
            offers_count=int(row[3]),
        )
        for row in rows
    )


def _raw_price_bound(connection: sqlite3.Connection, aggregate: str) -> float | None:
    if aggregate not in {"MIN", "MAX"} or not _table_exists(connection, RAW_OFFERS_TABLE):
        return None

    row = connection.execute(
        f"""
        SELECT {aggregate}(price_per_1000)
        FROM {RAW_OFFERS_TABLE}
        WHERE price_per_1000 IS NOT NULL
        """
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else None


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None
