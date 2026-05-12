from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(slots=True)
class Product:
    id: int
    game_type: str
    server: str
    faction: str
    price: str
    is_active: bool
    created_at: str
    updated_at: str

    @property
    def realm_type(self) -> str:
        return self.game_type

    @property
    def side(self) -> str:
        return self.faction


class ProductsRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def init_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                realm_type TEXT NOT NULL,
                server TEXT NOT NULL,
                side TEXT NOT NULL,
                price TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_columns(
            self._connection,
            "products",
            {
                "is_active": "INTEGER NOT NULL DEFAULT 1",
            },
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_products_catalog
            ON products(realm_type, server, side, is_active)
            """
        )

    def create_product(
        self,
        *,
        game_type: str,
        server: str,
        faction: str,
        price: str,
    ) -> Product:
        cursor = self._connection.execute(
            """
            INSERT INTO products (realm_type, server, side, price)
            VALUES (?, ?, ?, ?)
            """,
            (game_type, server, faction, price),
        )
        product_id = int(cursor.lastrowid)
        row = self._select_product(product_id)
        return _product_from_row(row)

    def count_products(self) -> int:
        row = self._connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM products
            WHERE is_active = 1
            """
        ).fetchone()

        return int(row["count"])

    def latest_products(self, limit: int, *, include_inactive: bool = False) -> list[Product]:
        inactive_filter = "" if include_inactive else "WHERE is_active = 1"
        rows = self._connection.execute(
            f"""
            SELECT id, realm_type, server, side, price, is_active, created_at, updated_at
            FROM products
            {inactive_filter}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [_product_from_row(row) for row in rows]

    def list_servers(self, game_type: str) -> list[str]:
        rows = self._connection.execute(
            """
            SELECT DISTINCT server
            FROM products
            WHERE realm_type = ? AND is_active = 1
            ORDER BY server COLLATE NOCASE
            """,
            (game_type,),
        ).fetchall()

        return [str(row["server"]) for row in rows]

    def list_sides(self, game_type: str, server: str) -> list[str]:
        rows = self._connection.execute(
            """
            SELECT DISTINCT side
            FROM products
            WHERE realm_type = ? AND server = ? AND is_active = 1
            ORDER BY side COLLATE NOCASE
            """,
            (game_type, server),
        ).fetchall()

        return [str(row["side"]) for row in rows]

    def list_products(self, game_type: str, server: str, faction: str) -> list[Product]:
        rows = self._connection.execute(
            """
            SELECT id, realm_type, server, side, price, is_active, created_at, updated_at
            FROM products
            WHERE realm_type = ? AND server = ? AND side = ? AND is_active = 1
            ORDER BY created_at DESC, id DESC
            """,
            (game_type, server, faction),
        ).fetchall()

        return [_product_from_row(row) for row in rows]

    def get_product(self, product_id: int, *, include_inactive: bool = False) -> Product | None:
        row = self._select_product(product_id, include_inactive=include_inactive)
        return _product_from_row(row) if row else None

    def update_price(self, *, product_id: int, price: str) -> Product | None:
        self._connection.execute(
            """
            UPDATE products
            SET price = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (price, product_id),
        )
        row = self._select_product(product_id, include_inactive=True)
        return _product_from_row(row) if row else None

    def set_active(self, *, product_id: int, is_active: bool) -> Product | None:
        self._connection.execute(
            """
            UPDATE products
            SET is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (1 if is_active else 0, product_id),
        )
        row = self._select_product(product_id, include_inactive=True)
        return _product_from_row(row) if row else None

    def _select_product(self, product_id: int, *, include_inactive: bool = False) -> sqlite3.Row | None:
        inactive_filter = "" if include_inactive else "AND is_active = 1"
        return self._connection.execute(
            f"""
            SELECT id, realm_type, server, side, price, is_active, created_at, updated_at
            FROM products
            WHERE id = ? {inactive_filter}
            """,
            (product_id,),
        ).fetchone()


def _product_from_row(row: sqlite3.Row) -> Product:
    return Product(
        id=int(row["id"]),
        game_type=row["realm_type"],
        server=row["server"],
        faction=row["side"],
        price=row["price"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _ensure_columns(
    connection: sqlite3.Connection,
    table_name: str,
    columns: dict[str, str],
) -> None:
    existing_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for column_name, column_definition in columns.items():
        if column_name not in existing_columns:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
