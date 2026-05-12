import asyncio
import sqlite3

from g_market_azeroth.database import MarketRepository


def test_init_adds_is_active_to_existing_products_table(tmp_path) -> None:
    database_path = tmp_path / "market.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                realm_type TEXT NOT NULL,
                server TEXT NOT NULL,
                side TEXT NOT NULL,
                price TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO products (realm_type, server, side, price)
            VALUES ('off', 'Soulseeker', 'Alliance', '120 ₽')
            """
        )

    asyncio.run(MarketRepository(database_path).init())

    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(products)").fetchall()}
        is_active = connection.execute("SELECT is_active FROM products").fetchone()[0]

    assert "is_active" in columns
    assert is_active == 1


def test_inactive_products_are_hidden_from_client_catalog(tmp_path) -> None:
    repository = MarketRepository(tmp_path / "market.sqlite3")
    asyncio.run(repository.init())
    active_product = asyncio.run(
        repository.create_catalog_product(
            realm_type="off",
            server="Soulseeker",
            side="Alliance",
            price="120 ₽",
        )
    )
    inactive_product = asyncio.run(
        repository.create_catalog_product(
            realm_type="off",
            server="Nek'Rosh",
            side="Horde",
            price="110 ₽",
        )
    )

    asyncio.run(repository.set_product_active(product_id=inactive_product.id, is_active=False))

    catalog_products = asyncio.run(
        repository.list_catalog_products(
            realm_type="off",
            server="Nek'Rosh",
            side="Horde",
        )
    )
    admin_products = asyncio.run(repository.latest_products(limit=10))

    assert catalog_products == []
    assert asyncio.run(repository.get_catalog_product(inactive_product.id)) is None
    assert [product.id for product in admin_products] == [inactive_product.id, active_product.id]
    assert admin_products[0].is_active is False
