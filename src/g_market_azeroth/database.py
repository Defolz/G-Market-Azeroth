from __future__ import annotations

import asyncio
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from g_market_azeroth.repositories.products import Product, ProductsRepository
from g_market_azeroth.repositories.requests import (
    PurchaseRequest,
    PurchaseRequestDetails,
    RequestsRepository,
    SellRequestDetails,
)
from g_market_azeroth.services.products import ProductService


@dataclass(frozen=True)
class Client:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language_code: str | None
    is_bot: bool
    start_count: int
    created_at: str
    updated_at: str
    last_seen_at: str


@dataclass(frozen=True)
class SupportTicket:
    id: int
    telegram_id: int
    status: str
    question: str
    answer: str | None
    admin_id: int | None
    created_at: str
    updated_at: str
    answered_at: str | None
    closed_at: str | None
    client_username: str | None = None
    client_first_name: str | None = None
    client_last_name: str | None = None


class MarketRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    async def upsert_client(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None,
        is_bot: bool,
    ) -> None:
        await asyncio.to_thread(
            self._upsert_client_sync,
            telegram_id,
            username,
            first_name,
            last_name,
            language_code,
            is_bot,
        )

    async def count_clients(self) -> int:
        return await asyncio.to_thread(self._count_clients_sync)

    async def latest_clients(self, limit: int = 10) -> list[Client]:
        return await asyncio.to_thread(self._latest_clients_sync, limit)

    async def add_product(
        self,
        *,
        realm_type: str,
        server: str,
        side: str,
        price: str,
    ) -> Product:
        return await self.create_catalog_product(
            realm_type=realm_type,
            server=server,
            side=side,
            price=price,
        )

    async def create_catalog_product(
        self,
        *,
        realm_type: str,
        server: str,
        side: str,
        price: str,
    ) -> Product:
        return await asyncio.to_thread(
            self._create_catalog_product_sync,
            realm_type,
            server,
            side,
            price,
        )

    async def count_products(self) -> int:
        return await asyncio.to_thread(self._count_products_sync)

    async def latest_products(self, limit: int = 10) -> list[Product]:
        return await self.list_catalog_products(limit=limit)

    async def list_servers(self, realm_type: str) -> list[str]:
        return await asyncio.to_thread(self._list_servers_sync, realm_type)

    async def list_sides(self, realm_type: str, server: str) -> list[str]:
        return await asyncio.to_thread(self._list_sides_sync, realm_type, server)

    async def list_products(self, realm_type: str, server: str, side: str) -> list[Product]:
        return await self.list_catalog_products(
            realm_type=realm_type,
            server=server,
            side=side,
        )

    async def list_catalog_products(
        self,
        *,
        realm_type: str | None = None,
        server: str | None = None,
        side: str | None = None,
        limit: int | None = None,
    ) -> list[Product]:
        return await asyncio.to_thread(
            self._list_catalog_products_sync,
            realm_type,
            server,
            side,
            limit,
        )

    async def get_product(self, product_id: int) -> Product | None:
        return await self.get_catalog_product(product_id)

    async def get_catalog_product(self, product_id: int) -> Product | None:
        return await asyncio.to_thread(self._get_catalog_product_sync, product_id)

    async def update_product_price(self, *, product_id: int, price: str) -> Product | None:
        return await self.change_product_price(product_id=product_id, price=price)

    async def change_product_price(self, *, product_id: int, price: str) -> Product | None:
        return await asyncio.to_thread(self._change_product_price_sync, product_id, price)

    async def create_purchase_request(self, *, product_id: int, telegram_id: int) -> PurchaseRequest:
        return await asyncio.to_thread(
            self._create_purchase_request_sync,
            product_id,
            telegram_id,
        )

    async def count_purchase_requests(self, status: str | None = None) -> int:
        return await asyncio.to_thread(self._count_purchase_requests_sync, status)

    async def latest_purchase_requests(self, limit: int = 10) -> list[PurchaseRequestDetails]:
        return await asyncio.to_thread(self._latest_purchase_requests_sync, limit)

    async def latest_purchase_requests_by_user(
        self,
        telegram_id: int,
        limit: int = 10,
    ) -> list[PurchaseRequestDetails]:
        return await asyncio.to_thread(self._latest_purchase_requests_by_user_sync, telegram_id, limit)

    async def get_purchase_request(self, request_id: int) -> PurchaseRequestDetails | None:
        return await asyncio.to_thread(self._get_purchase_request_sync, request_id)

    async def update_purchase_request_status(
        self,
        *,
        request_id: int,
        status: str,
    ) -> PurchaseRequestDetails | None:
        return await asyncio.to_thread(self._update_purchase_request_status_sync, request_id, status)

    async def create_sell_request(
        self,
        *,
        telegram_id: int,
        realm_type: str,
        server: str,
        side: str,
        amount: str,
        price: str,
        comment: str | None,
    ) -> SellRequestDetails:
        return await asyncio.to_thread(
            self._create_sell_request_sync,
            telegram_id,
            realm_type,
            server,
            side,
            amount,
            price,
            comment,
        )

    async def count_sell_requests(self, status: str | None = None) -> int:
        return await asyncio.to_thread(self._count_sell_requests_sync, status)

    async def latest_sell_requests(self, limit: int = 10) -> list[SellRequestDetails]:
        return await asyncio.to_thread(self._latest_sell_requests_sync, limit)

    async def latest_sell_requests_by_user(
        self,
        telegram_id: int,
        limit: int = 10,
    ) -> list[SellRequestDetails]:
        return await asyncio.to_thread(self._latest_sell_requests_by_user_sync, telegram_id, limit)

    async def get_sell_request(self, request_id: int) -> SellRequestDetails | None:
        return await asyncio.to_thread(self._get_sell_request_sync, request_id)

    async def update_sell_request_status(
        self,
        *,
        request_id: int,
        status: str,
    ) -> SellRequestDetails | None:
        return await asyncio.to_thread(self._update_sell_request_status_sync, request_id, status)

    async def create_support_ticket(self, *, telegram_id: int, question: str) -> SupportTicket:
        return await asyncio.to_thread(self._create_support_ticket_sync, telegram_id, question)

    async def count_support_tickets(self, status: str | None = None) -> int:
        return await asyncio.to_thread(self._count_support_tickets_sync, status)

    async def latest_support_tickets(self, limit: int = 10) -> list[SupportTicket]:
        return await asyncio.to_thread(self._latest_support_tickets_sync, limit)

    async def latest_support_tickets_by_user(
        self,
        telegram_id: int,
        limit: int = 10,
    ) -> list[SupportTicket]:
        return await asyncio.to_thread(self._latest_support_tickets_by_user_sync, telegram_id, limit)

    async def get_support_ticket(self, ticket_id: int) -> SupportTicket | None:
        return await asyncio.to_thread(self._get_support_ticket_sync, ticket_id)

    async def answer_support_ticket(
        self,
        *,
        ticket_id: int,
        admin_id: int,
        answer: str,
    ) -> SupportTicket | None:
        return await asyncio.to_thread(
            self._answer_support_ticket_sync,
            ticket_id,
            admin_id,
            answer,
        )

    async def close_support_ticket(self, *, ticket_id: int, admin_id: int) -> SupportTicket | None:
        return await asyncio.to_thread(self._close_support_ticket_sync, ticket_id, admin_id)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init_sync(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)

        with closing(self._connect()) as connection:
            self._create_clients_table(connection)
            self._create_products_table(connection)
            self._create_purchase_requests_table(connection)
            self._create_sell_requests_table(connection)
            self._create_support_tickets_table(connection)
            connection.commit()

    def _create_clients_table(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS clients (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT,
                is_bot INTEGER NOT NULL DEFAULT 0,
                start_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_clients_last_seen_at
            ON clients(last_seen_at DESC)
            """
        )

    def _create_products_table(self, connection: sqlite3.Connection) -> None:
        ProductsRepository(connection).init_schema()

    def _create_purchase_requests_table(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS purchase_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                telegram_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                price_snapshot TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT,
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
            """
        )
        self._ensure_columns(
            connection,
            "purchase_requests",
            {
                "price_snapshot": "TEXT",
                "updated_at": "TEXT",
                "closed_at": "TEXT",
            },
        )
        connection.execute(
            """
            UPDATE purchase_requests
            SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
            WHERE updated_at IS NULL
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_purchase_requests_created_at
            ON purchase_requests(created_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_purchase_requests_telegram_id
            ON purchase_requests(telegram_id, created_at DESC)
            """
        )

    def _create_sell_requests_table(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sell_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                realm_type TEXT NOT NULL,
                server TEXT NOT NULL,
                side TEXT NOT NULL,
                amount TEXT NOT NULL,
                price TEXT NOT NULL,
                comment TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sell_requests_created_at
            ON sell_requests(created_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sell_requests_telegram_id
            ON sell_requests(telegram_id, created_at DESC)
            """
        )

    def _create_support_tickets_table(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                question TEXT NOT NULL,
                answer TEXT,
                admin_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                answered_at TEXT,
                closed_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_support_tickets_created_at
            ON support_tickets(created_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_support_tickets_telegram_id
            ON support_tickets(telegram_id, created_at DESC)
            """
        )

    def _ensure_columns(
        self,
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
                connection.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                )

    def _upsert_client_sync(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None,
        is_bot: bool,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO clients (
                    telegram_id,
                    username,
                    first_name,
                    last_name,
                    language_code,
                    is_bot,
                    start_count
                )
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    language_code = excluded.language_code,
                    is_bot = excluded.is_bot,
                    start_count = clients.start_count + 1,
                    updated_at = CURRENT_TIMESTAMP,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (
                    telegram_id,
                    username,
                    first_name,
                    last_name,
                    language_code,
                    int(is_bot),
                ),
            )
            connection.commit()

    def _count_clients_sync(self) -> int:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM clients").fetchone()

        return int(row["count"])

    def _latest_clients_sync(self, limit: int) -> list[Client]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    telegram_id,
                    username,
                    first_name,
                    last_name,
                    language_code,
                    is_bot,
                    start_count,
                    created_at,
                    updated_at,
                    last_seen_at
                FROM clients
                ORDER BY last_seen_at DESC, created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [_client_from_row(row) for row in rows]

    def _create_catalog_product_sync(self, realm_type: str, server: str, side: str, price: str) -> Product:
        with closing(self._connect()) as connection:
            product = ProductService(ProductsRepository(connection)).create_catalog_product(
                realm_type=realm_type,
                server=server,
                side=side,
                price=price,
            )
            connection.commit()

        return product

    def _count_products_sync(self) -> int:
        with closing(self._connect()) as connection:
            return ProductsRepository(connection).count_products()

    def _list_servers_sync(self, realm_type: str) -> list[str]:
        with closing(self._connect()) as connection:
            return ProductsRepository(connection).list_servers(realm_type)

    def _list_sides_sync(self, realm_type: str, server: str) -> list[str]:
        with closing(self._connect()) as connection:
            return ProductsRepository(connection).list_sides(realm_type, server)

    def _list_catalog_products_sync(
        self,
        realm_type: str | None,
        server: str | None,
        side: str | None,
        limit: int | None,
    ) -> list[Product]:
        with closing(self._connect()) as connection:
            return ProductService(ProductsRepository(connection)).list_catalog_products(
                realm_type=realm_type,
                server=server,
                side=side,
                limit=limit,
            )

    def _get_catalog_product_sync(self, product_id: int) -> Product | None:
        with closing(self._connect()) as connection:
            return ProductService(ProductsRepository(connection)).get_catalog_product(product_id)

    def _change_product_price_sync(self, product_id: int, price: str) -> Product | None:
        with closing(self._connect()) as connection:
            product = ProductService(ProductsRepository(connection)).change_product_price(
                product_id=product_id,
                price=price,
            )
            connection.commit()

        return product

    def _create_purchase_request_sync(self, product_id: int, telegram_id: int) -> PurchaseRequest:
        with closing(self._connect()) as connection:
            request = RequestsRepository(connection).create_purchase_request(
                product_id=product_id,
                telegram_id=telegram_id,
            )
            connection.commit()

        return request

    def _count_purchase_requests_sync(self, status: str | None = None) -> int:
        with closing(self._connect()) as connection:
            return RequestsRepository(connection).count_purchase_requests(status)

    def _latest_purchase_requests_sync(self, limit: int) -> list[PurchaseRequestDetails]:
        with closing(self._connect()) as connection:
            return RequestsRepository(connection).latest_purchase_requests(limit)

    def _latest_purchase_requests_by_user_sync(
        self,
        telegram_id: int,
        limit: int,
    ) -> list[PurchaseRequestDetails]:
        with closing(self._connect()) as connection:
            return RequestsRepository(connection).latest_purchase_requests_by_user(
                telegram_id=telegram_id,
                limit=limit,
            )

    def _get_purchase_request_sync(self, request_id: int) -> PurchaseRequestDetails | None:
        with closing(self._connect()) as connection:
            return RequestsRepository(connection).get_purchase_request(request_id)

    def _update_purchase_request_status_sync(
        self,
        request_id: int,
        status: str,
    ) -> PurchaseRequestDetails | None:
        with closing(self._connect()) as connection:
            request = RequestsRepository(connection).update_purchase_request_status(
                request_id=request_id,
                status=status,
            )
            connection.commit()

        return request

    def _create_sell_request_sync(
        self,
        telegram_id: int,
        realm_type: str,
        server: str,
        side: str,
        amount: str,
        price: str,
        comment: str | None,
    ) -> SellRequestDetails:
        with closing(self._connect()) as connection:
            request = RequestsRepository(connection).create_sell_request(
                telegram_id=telegram_id,
                realm_type=realm_type,
                server=server,
                side=side,
                amount=amount,
                price=price,
                comment=comment,
            )
            connection.commit()

        return request

    def _count_sell_requests_sync(self, status: str | None = None) -> int:
        with closing(self._connect()) as connection:
            return RequestsRepository(connection).count_sell_requests(status)

    def _latest_sell_requests_sync(self, limit: int) -> list[SellRequestDetails]:
        with closing(self._connect()) as connection:
            return RequestsRepository(connection).latest_sell_requests(limit)

    def _latest_sell_requests_by_user_sync(
        self,
        telegram_id: int,
        limit: int,
    ) -> list[SellRequestDetails]:
        with closing(self._connect()) as connection:
            return RequestsRepository(connection).latest_sell_requests_by_user(
                telegram_id=telegram_id,
                limit=limit,
            )

    def _get_sell_request_sync(self, request_id: int) -> SellRequestDetails | None:
        with closing(self._connect()) as connection:
            return RequestsRepository(connection).get_sell_request(request_id)

    def _update_sell_request_status_sync(
        self,
        request_id: int,
        status: str,
    ) -> SellRequestDetails | None:
        with closing(self._connect()) as connection:
            request = RequestsRepository(connection).update_sell_request_status(
                request_id=request_id,
                status=status,
            )
            connection.commit()

        return request

    def _create_support_ticket_sync(self, telegram_id: int, question: str) -> SupportTicket:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO support_tickets (telegram_id, question)
                VALUES (?, ?)
                """,
                (telegram_id, question),
            )
            ticket_id = int(cursor.lastrowid)
            row = self._select_support_tickets(connection, ticket_id=ticket_id).fetchone()
            connection.commit()

        return _support_ticket_from_row(row)

    def _count_support_tickets_sync(self, status: str | None = None) -> int:
        with closing(self._connect()) as connection:
            if status:
                row = connection.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM support_tickets
                    WHERE status = ?
                    """,
                    (status,),
                ).fetchone()
            else:
                row = connection.execute("SELECT COUNT(*) AS count FROM support_tickets").fetchone()

        return int(row["count"])

    def _latest_support_tickets_sync(self, limit: int) -> list[SupportTicket]:
        with closing(self._connect()) as connection:
            rows = self._select_support_tickets(connection, limit=limit).fetchall()

        return [_support_ticket_from_row(row) for row in rows]

    def _latest_support_tickets_by_user_sync(
        self,
        telegram_id: int,
        limit: int,
    ) -> list[SupportTicket]:
        with closing(self._connect()) as connection:
            rows = self._select_support_tickets(
                connection,
                limit=limit,
                telegram_id=telegram_id,
            ).fetchall()

        return [_support_ticket_from_row(row) for row in rows]

    def _get_support_ticket_sync(self, ticket_id: int) -> SupportTicket | None:
        with closing(self._connect()) as connection:
            row = self._select_support_tickets(connection, ticket_id=ticket_id).fetchone()

        return _support_ticket_from_row(row) if row else None

    def _answer_support_ticket_sync(
        self,
        ticket_id: int,
        admin_id: int,
        answer: str,
    ) -> SupportTicket | None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE support_tickets
                SET
                    status = 'answered',
                    answer = ?,
                    admin_id = ?,
                    answered_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (answer, admin_id, ticket_id),
            )
            row = self._select_support_tickets(connection, ticket_id=ticket_id).fetchone()
            connection.commit()

        return _support_ticket_from_row(row) if row else None

    def _close_support_ticket_sync(self, ticket_id: int, admin_id: int) -> SupportTicket | None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE support_tickets
                SET
                    status = 'closed',
                    admin_id = ?,
                    closed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (admin_id, ticket_id),
            )
            row = self._select_support_tickets(connection, ticket_id=ticket_id).fetchone()
            connection.commit()

        return _support_ticket_from_row(row) if row else None

    def _select_support_tickets(
        self,
        connection: sqlite3.Connection,
        *,
        limit: int | None = None,
        ticket_id: int | None = None,
        telegram_id: int | None = None,
    ) -> sqlite3.Cursor:
        where_parts: list[str] = []
        params: list[int] = []
        if ticket_id is not None:
            where_parts.append("ticket.id = ?")
            params.append(ticket_id)
        if telegram_id is not None:
            where_parts.append("ticket.telegram_id = ?")
            params.append(telegram_id)

        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        limit_sql = "LIMIT ?" if limit is not None else ""
        if limit is not None:
            params.append(limit)

        return connection.execute(
            f"""
            SELECT
                ticket.id AS ticket_id,
                ticket.telegram_id AS ticket_telegram_id,
                ticket.status AS ticket_status,
                ticket.question AS ticket_question,
                ticket.answer AS ticket_answer,
                ticket.admin_id AS ticket_admin_id,
                ticket.created_at AS ticket_created_at,
                ticket.updated_at AS ticket_updated_at,
                ticket.answered_at AS ticket_answered_at,
                ticket.closed_at AS ticket_closed_at,
                client.username AS client_username,
                client.first_name AS client_first_name,
                client.last_name AS client_last_name
            FROM support_tickets AS ticket
            LEFT JOIN clients AS client ON client.telegram_id = ticket.telegram_id
            {where_sql}
            ORDER BY ticket.created_at DESC, ticket.id DESC
            {limit_sql}
            """,
            params,
        )


ClientRepository = MarketRepository


def _client_from_row(row: sqlite3.Row) -> Client:
    return Client(
        telegram_id=int(row["telegram_id"]),
        username=row["username"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        language_code=row["language_code"],
        is_bot=bool(row["is_bot"]),
        start_count=int(row["start_count"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_seen_at=row["last_seen_at"],
    )


def _support_ticket_from_row(row: sqlite3.Row) -> SupportTicket:
    return SupportTicket(
        id=int(row["ticket_id"]),
        telegram_id=int(row["ticket_telegram_id"]),
        status=row["ticket_status"],
        question=row["ticket_question"],
        answer=row["ticket_answer"],
        admin_id=int(row["ticket_admin_id"]) if row["ticket_admin_id"] is not None else None,
        created_at=row["ticket_created_at"],
        updated_at=row["ticket_updated_at"],
        answered_at=row["ticket_answered_at"],
        closed_at=row["ticket_closed_at"],
        client_username=row["client_username"],
        client_first_name=row["client_first_name"],
        client_last_name=row["client_last_name"],
    )
