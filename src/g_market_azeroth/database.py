from __future__ import annotations

import asyncio
import sqlite3
from contextlib import closing
from pathlib import Path

from g_market_azeroth.repositories.catalog_sync_audit import CatalogSyncAudit, CatalogSyncAuditRepository
from g_market_azeroth.repositories.clients import Client, ClientsRepository
from g_market_azeroth.repositories.products import Product, ProductsRepository
from g_market_azeroth.repositories.requests import (
    PurchaseRequest,
    PurchaseRequestDetails,
    RequestsRepository,
    SellRequestDetails,
)
from g_market_azeroth.repositories.support import SupportMessage, SupportRepository, SupportTicket
from g_market_azeroth.services.products import ProductService


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

    async def get_client(self, telegram_id: int) -> Client | None:
        return await asyncio.to_thread(self._get_client_sync, telegram_id)

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
        return await asyncio.to_thread(self._latest_products_sync, limit)

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

    async def set_product_active(self, *, product_id: int, is_active: bool) -> Product | None:
        return await asyncio.to_thread(self._set_product_active_sync, product_id, is_active)

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

    async def add_support_message(
        self,
        *,
        ticket_id: int,
        sender_type: str,
        sender_id: int,
        message: str,
    ) -> SupportMessage:
        return await asyncio.to_thread(
            self._add_support_message_sync,
            ticket_id,
            sender_type,
            sender_id,
            message,
        )

    async def list_support_messages(self, ticket_id: int) -> list[SupportMessage]:
        return await asyncio.to_thread(self._list_support_messages_sync, ticket_id)

    async def create_catalog_sync_audit(
        self,
        *,
        admin_telegram_id: int,
        created_count: int,
        updated_count: int,
        hidden_count: int,
        error_count: int,
        status: str,
    ) -> CatalogSyncAudit:
        return await asyncio.to_thread(
            self._create_catalog_sync_audit_sync,
            admin_telegram_id,
            created_count,
            updated_count,
            hidden_count,
            error_count,
            status,
        )

    async def latest_catalog_sync_audits(self, limit: int = 10) -> list[CatalogSyncAudit]:
        return await asyncio.to_thread(self._latest_catalog_sync_audits_sync, limit)

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
            self._create_catalog_sync_audit_table(connection)
            connection.commit()

    def _create_clients_table(self, connection: sqlite3.Connection) -> None:
        ClientsRepository(connection).init_schema()

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
        SupportRepository(connection).init_schema()

    def _create_catalog_sync_audit_table(self, connection: sqlite3.Connection) -> None:
        CatalogSyncAuditRepository(connection).init_schema()

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
            ClientsRepository(connection).upsert_client(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
                is_bot=is_bot,
            )
            connection.commit()

    def _count_clients_sync(self) -> int:
        with closing(self._connect()) as connection:
            return ClientsRepository(connection).count_clients()

    def _get_client_sync(self, telegram_id: int) -> Client | None:
        with closing(self._connect()) as connection:
            return ClientsRepository(connection).get_client(telegram_id)

    def _latest_clients_sync(self, limit: int) -> list[Client]:
        with closing(self._connect()) as connection:
            return ClientsRepository(connection).latest_clients(limit)

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

    def _latest_products_sync(self, limit: int) -> list[Product]:
        with closing(self._connect()) as connection:
            return ProductService(ProductsRepository(connection)).list_admin_products(limit=limit)

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

    def _set_product_active_sync(self, product_id: int, is_active: bool) -> Product | None:
        with closing(self._connect()) as connection:
            product = ProductService(ProductsRepository(connection)).set_product_active(
                product_id=product_id,
                is_active=is_active,
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
            ticket = SupportRepository(connection).create_ticket(
                telegram_id=telegram_id,
                question=question,
            )
            connection.commit()

        return ticket

    def _count_support_tickets_sync(self, status: str | None = None) -> int:
        with closing(self._connect()) as connection:
            return SupportRepository(connection).count_tickets(status)

    def _latest_support_tickets_sync(self, limit: int) -> list[SupportTicket]:
        with closing(self._connect()) as connection:
            return SupportRepository(connection).latest_tickets(limit)

    def _latest_support_tickets_by_user_sync(
        self,
        telegram_id: int,
        limit: int,
    ) -> list[SupportTicket]:
        with closing(self._connect()) as connection:
            return SupportRepository(connection).latest_tickets_by_user(
                telegram_id=telegram_id,
                limit=limit,
            )

    def _get_support_ticket_sync(self, ticket_id: int) -> SupportTicket | None:
        with closing(self._connect()) as connection:
            return SupportRepository(connection).get_ticket(ticket_id)

    def _answer_support_ticket_sync(
        self,
        ticket_id: int,
        admin_id: int,
        answer: str,
    ) -> SupportTicket | None:
        with closing(self._connect()) as connection:
            ticket = SupportRepository(connection).answer_ticket(
                ticket_id=ticket_id,
                admin_id=admin_id,
                answer=answer,
            )
            connection.commit()

        return ticket

    def _close_support_ticket_sync(self, ticket_id: int, admin_id: int) -> SupportTicket | None:
        with closing(self._connect()) as connection:
            ticket = SupportRepository(connection).close_ticket(
                ticket_id=ticket_id,
                admin_id=admin_id,
            )
            connection.commit()

        return ticket

    def _add_support_message_sync(
        self,
        ticket_id: int,
        sender_type: str,
        sender_id: int,
        message: str,
    ) -> SupportMessage:
        with closing(self._connect()) as connection:
            support_message = SupportRepository(connection).add_support_message(
                ticket_id=ticket_id,
                sender_type=sender_type,
                sender_id=sender_id,
                message=message,
            )
            connection.commit()

        return support_message

    def _list_support_messages_sync(self, ticket_id: int) -> list[SupportMessage]:
        with closing(self._connect()) as connection:
            return SupportRepository(connection).list_support_messages(ticket_id)

    def _create_catalog_sync_audit_sync(
        self,
        admin_telegram_id: int,
        created_count: int,
        updated_count: int,
        hidden_count: int,
        error_count: int,
        status: str,
    ) -> CatalogSyncAudit:
        with closing(self._connect()) as connection:
            audit = CatalogSyncAuditRepository(connection).create(
                admin_telegram_id=admin_telegram_id,
                created_count=created_count,
                updated_count=updated_count,
                hidden_count=hidden_count,
                error_count=error_count,
                status=status,
            )
            connection.commit()

        return audit

    def _latest_catalog_sync_audits_sync(self, limit: int) -> list[CatalogSyncAudit]:
        with closing(self._connect()) as connection:
            return CatalogSyncAuditRepository(connection).latest(limit)


ClientRepository = MarketRepository
