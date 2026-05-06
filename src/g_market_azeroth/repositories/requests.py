from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from g_market_azeroth.repositories.products import Product


@dataclass(frozen=True)
class PurchaseRequest:
    id: int
    product_id: int
    telegram_id: int
    status: str
    price_snapshot: str | None
    created_at: str
    updated_at: str
    closed_at: str | None


@dataclass(frozen=True)
class PurchaseRequestDetails:
    id: int
    status: str
    created_at: str
    updated_at: str
    closed_at: str | None
    telegram_id: int
    price_snapshot: str | None
    client_username: str | None
    client_first_name: str | None
    client_last_name: str | None
    product: Product


@dataclass(frozen=True)
class SellRequestDetails:
    id: int
    telegram_id: int
    status: str
    realm_type: str
    server: str
    side: str
    amount: str
    price: str
    comment: str | None
    created_at: str
    updated_at: str
    closed_at: str | None
    client_username: str | None
    client_first_name: str | None
    client_last_name: str | None


class RequestsRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_purchase_request(self, *, product_id: int, telegram_id: int) -> PurchaseRequest:
        product_row = self._connection.execute(
            """
            SELECT price
            FROM products
            WHERE id = ?
            """,
            (product_id,),
        ).fetchone()
        cursor = self._connection.execute(
            """
            INSERT INTO purchase_requests (product_id, telegram_id, price_snapshot)
            VALUES (?, ?, ?)
            """,
            (
                product_id,
                telegram_id,
                product_row["price"] if product_row else None,
            ),
        )
        request_id = int(cursor.lastrowid)
        row = self._connection.execute(
            """
            SELECT id, product_id, telegram_id, status, price_snapshot, created_at, updated_at, closed_at
            FROM purchase_requests
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()

        return _purchase_request_from_row(row)

    def count_purchase_requests(self, status: str | None = None) -> int:
        if status:
            row = self._connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM purchase_requests
                WHERE status = ?
                """,
                (status,),
            ).fetchone()
        else:
            row = self._connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM purchase_requests
                """
            ).fetchone()

        return int(row["count"])

    def latest_purchase_requests(self, limit: int) -> list[PurchaseRequestDetails]:
        rows = self._select_purchase_requests(limit=limit).fetchall()
        return [_purchase_request_details_from_row(row) for row in rows]

    def latest_purchase_requests_by_user(
        self,
        telegram_id: int,
        limit: int,
    ) -> list[PurchaseRequestDetails]:
        rows = self._select_purchase_requests(limit=limit, telegram_id=telegram_id).fetchall()
        return [_purchase_request_details_from_row(row) for row in rows]

    def get_purchase_request(self, request_id: int) -> PurchaseRequestDetails | None:
        row = self._select_purchase_requests(request_id=request_id).fetchone()
        return _purchase_request_details_from_row(row) if row else None

    def update_purchase_request_status(
        self,
        *,
        request_id: int,
        status: str,
    ) -> PurchaseRequestDetails | None:
        closed_at_sql = "CURRENT_TIMESTAMP" if status in {"completed", "cancelled"} else "NULL"
        self._connection.execute(
            f"""
            UPDATE purchase_requests
            SET status = ?, updated_at = CURRENT_TIMESTAMP, closed_at = {closed_at_sql}
            WHERE id = ?
            """,
            (status, request_id),
        )
        row = self._select_purchase_requests(request_id=request_id).fetchone()
        return _purchase_request_details_from_row(row) if row else None

    def create_sell_request(
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
        cursor = self._connection.execute(
            """
            INSERT INTO sell_requests (
                telegram_id,
                realm_type,
                server,
                side,
                amount,
                price,
                comment
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (telegram_id, realm_type, server, side, amount, price, comment),
        )
        request_id = int(cursor.lastrowid)
        row = self._select_sell_requests(request_id=request_id).fetchone()

        return _sell_request_details_from_row(row)

    def count_sell_requests(self, status: str | None = None) -> int:
        if status:
            row = self._connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM sell_requests
                WHERE status = ?
                """,
                (status,),
            ).fetchone()
        else:
            row = self._connection.execute("SELECT COUNT(*) AS count FROM sell_requests").fetchone()

        return int(row["count"])

    def latest_sell_requests(self, limit: int) -> list[SellRequestDetails]:
        rows = self._select_sell_requests(limit=limit).fetchall()
        return [_sell_request_details_from_row(row) for row in rows]

    def latest_sell_requests_by_user(
        self,
        telegram_id: int,
        limit: int,
    ) -> list[SellRequestDetails]:
        rows = self._select_sell_requests(limit=limit, telegram_id=telegram_id).fetchall()
        return [_sell_request_details_from_row(row) for row in rows]

    def get_sell_request(self, request_id: int) -> SellRequestDetails | None:
        row = self._select_sell_requests(request_id=request_id).fetchone()
        return _sell_request_details_from_row(row) if row else None

    def update_sell_request_status(
        self,
        *,
        request_id: int,
        status: str,
    ) -> SellRequestDetails | None:
        closed_at_sql = "CURRENT_TIMESTAMP" if status in {"completed", "cancelled"} else "NULL"
        self._connection.execute(
            f"""
            UPDATE sell_requests
            SET status = ?, updated_at = CURRENT_TIMESTAMP, closed_at = {closed_at_sql}
            WHERE id = ?
            """,
            (status, request_id),
        )
        row = self._select_sell_requests(request_id=request_id).fetchone()
        return _sell_request_details_from_row(row) if row else None

    def _select_purchase_requests(
        self,
        *,
        limit: int | None = None,
        request_id: int | None = None,
        telegram_id: int | None = None,
    ) -> sqlite3.Cursor:
        where_parts: list[str] = []
        params: list[int] = []
        if request_id is not None:
            where_parts.append("request.id = ?")
            params.append(request_id)
        if telegram_id is not None:
            where_parts.append("request.telegram_id = ?")
            params.append(telegram_id)

        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        limit_sql = "LIMIT ?" if limit is not None else ""
        if limit is not None:
            params.append(limit)

        return self._connection.execute(
            f"""
            SELECT
                request.id AS request_id,
                request.status AS request_status,
                request.created_at AS request_created_at,
                request.updated_at AS request_updated_at,
                request.closed_at AS request_closed_at,
                request.telegram_id AS request_telegram_id,
                COALESCE(request.price_snapshot, product.price) AS request_price_snapshot,
                client.username AS client_username,
                client.first_name AS client_first_name,
                client.last_name AS client_last_name,
                product.id AS product_id,
                product.realm_type AS product_realm_type,
                product.server AS product_server,
                product.side AS product_side,
                product.price AS product_price,
                product.is_active AS product_is_active,
                product.created_at AS product_created_at,
                product.updated_at AS product_updated_at
            FROM purchase_requests AS request
            JOIN products AS product ON product.id = request.product_id
            LEFT JOIN clients AS client ON client.telegram_id = request.telegram_id
            {where_sql}
            ORDER BY request.created_at DESC, request.id DESC
            {limit_sql}
            """,
            params,
        )

    def _select_sell_requests(
        self,
        *,
        limit: int | None = None,
        request_id: int | None = None,
        telegram_id: int | None = None,
    ) -> sqlite3.Cursor:
        where_parts: list[str] = []
        params: list[int] = []
        if request_id is not None:
            where_parts.append("request.id = ?")
            params.append(request_id)
        if telegram_id is not None:
            where_parts.append("request.telegram_id = ?")
            params.append(telegram_id)

        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        limit_sql = "LIMIT ?" if limit is not None else ""
        if limit is not None:
            params.append(limit)

        return self._connection.execute(
            f"""
            SELECT
                request.id AS request_id,
                request.telegram_id AS request_telegram_id,
                request.status AS request_status,
                request.realm_type AS request_realm_type,
                request.server AS request_server,
                request.side AS request_side,
                request.amount AS request_amount,
                request.price AS request_price,
                request.comment AS request_comment,
                request.created_at AS request_created_at,
                request.updated_at AS request_updated_at,
                request.closed_at AS request_closed_at,
                client.username AS client_username,
                client.first_name AS client_first_name,
                client.last_name AS client_last_name
            FROM sell_requests AS request
            LEFT JOIN clients AS client ON client.telegram_id = request.telegram_id
            {where_sql}
            ORDER BY request.created_at DESC, request.id DESC
            {limit_sql}
            """,
            params,
        )


def _purchase_request_from_row(row: sqlite3.Row) -> PurchaseRequest:
    return PurchaseRequest(
        id=int(row["id"]),
        product_id=int(row["product_id"]),
        telegram_id=int(row["telegram_id"]),
        status=row["status"],
        price_snapshot=row["price_snapshot"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        closed_at=row["closed_at"],
    )


def _purchase_request_details_from_row(row: sqlite3.Row) -> PurchaseRequestDetails:
    product = Product(
        id=int(row["product_id"]),
        game_type=row["product_realm_type"],
        server=row["product_server"],
        faction=row["product_side"],
        price=row["product_price"],
        is_active=bool(row["product_is_active"]),
        created_at=row["product_created_at"],
        updated_at=row["product_updated_at"],
    )

    return PurchaseRequestDetails(
        id=int(row["request_id"]),
        status=row["request_status"],
        created_at=row["request_created_at"],
        updated_at=row["request_updated_at"],
        closed_at=row["request_closed_at"],
        telegram_id=int(row["request_telegram_id"]),
        price_snapshot=row["request_price_snapshot"],
        client_username=row["client_username"],
        client_first_name=row["client_first_name"],
        client_last_name=row["client_last_name"],
        product=product,
    )


def _sell_request_details_from_row(row: sqlite3.Row) -> SellRequestDetails:
    return SellRequestDetails(
        id=int(row["request_id"]),
        telegram_id=int(row["request_telegram_id"]),
        status=row["request_status"],
        realm_type=row["request_realm_type"],
        server=row["request_server"],
        side=row["request_side"],
        amount=row["request_amount"],
        price=row["request_price"],
        comment=row["request_comment"],
        created_at=row["request_created_at"],
        updated_at=row["request_updated_at"],
        closed_at=row["request_closed_at"],
        client_username=row["client_username"],
        client_first_name=row["client_first_name"],
        client_last_name=row["client_last_name"],
    )
