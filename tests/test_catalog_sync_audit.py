import asyncio

from g_market_azeroth.database import MarketRepository


def test_init_creates_catalog_sync_audit_table(tmp_path) -> None:
    database = MarketRepository(tmp_path / "market.sqlite3")

    asyncio.run(database.init())
    audits = asyncio.run(database.latest_catalog_sync_audits(limit=10))

    assert audits == []


def test_create_catalog_sync_audit_stores_success_counts(tmp_path) -> None:
    database = MarketRepository(tmp_path / "market.sqlite3")
    asyncio.run(database.init())

    audit = asyncio.run(
        database.create_catalog_sync_audit(
            admin_telegram_id=1001,
            created_count=3,
            updated_count=12,
            hidden_count=2,
            error_count=0,
            status="success",
        )
    )

    assert audit.id == 1
    assert audit.admin_telegram_id == 1001
    assert audit.created_count == 3
    assert audit.updated_count == 12
    assert audit.hidden_count == 2
    assert audit.error_count == 0
    assert audit.status == "success"
    assert audit.created_at


def test_create_catalog_sync_audit_stores_failed_syncs(tmp_path) -> None:
    database = MarketRepository(tmp_path / "market.sqlite3")
    asyncio.run(database.init())

    audit = asyncio.run(
        database.create_catalog_sync_audit(
            admin_telegram_id=1001,
            created_count=0,
            updated_count=0,
            hidden_count=0,
            error_count=1,
            status="failed",
        )
    )

    assert audit.id == 1
    assert audit.error_count == 1
    assert audit.status == "failed"
