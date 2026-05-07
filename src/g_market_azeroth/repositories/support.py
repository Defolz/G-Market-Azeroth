from __future__ import annotations

import sqlite3
from dataclasses import dataclass


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


@dataclass(frozen=True)
class SupportMessage:
    id: int
    ticket_id: int
    sender_type: str
    sender_id: int
    message: str
    created_at: str


class SupportRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def init_schema(self) -> None:
        self._connection.execute(
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
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_support_tickets_created_at
            ON support_tickets(created_at DESC)
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_support_tickets_telegram_id
            ON support_tickets(telegram_id, created_at DESC)
            """
        )

    def create_ticket(self, *, telegram_id: int, question: str) -> SupportTicket:
        cursor = self._connection.execute(
            """
            INSERT INTO support_tickets (telegram_id, question)
            VALUES (?, ?)
            """,
            (telegram_id, question),
        )
        ticket_id = int(cursor.lastrowid)
        row = self._select_tickets(ticket_id=ticket_id).fetchone()

        return _support_ticket_from_row(row)

    def count_tickets(self, status: str | None = None) -> int:
        if status:
            row = self._connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM support_tickets
                WHERE status = ?
                """,
                (status,),
            ).fetchone()
        else:
            row = self._connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM support_tickets
                """
            ).fetchone()

        return int(row["count"])

    def latest_tickets(self, limit: int) -> list[SupportTicket]:
        rows = self._select_tickets(limit=limit).fetchall()
        return [_support_ticket_from_row(row) for row in rows]

    def latest_tickets_by_user(
        self,
        telegram_id: int,
        limit: int,
    ) -> list[SupportTicket]:
        rows = self._select_tickets(limit=limit, telegram_id=telegram_id).fetchall()
        return [_support_ticket_from_row(row) for row in rows]

    def get_ticket(self, ticket_id: int) -> SupportTicket | None:
        row = self._select_tickets(ticket_id=ticket_id).fetchone()
        return _support_ticket_from_row(row) if row else None

    def answer_ticket(
        self,
        *,
        ticket_id: int,
        admin_id: int,
        answer: str,
    ) -> SupportTicket | None:
        self._connection.execute(
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
        row = self._select_tickets(ticket_id=ticket_id).fetchone()
        return _support_ticket_from_row(row) if row else None

    def close_ticket(self, *, ticket_id: int, admin_id: int) -> SupportTicket | None:
        self._connection.execute(
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
        row = self._select_tickets(ticket_id=ticket_id).fetchone()
        return _support_ticket_from_row(row) if row else None

    def add_support_message(
        self,
        *,
        ticket_id: int,
        sender_type: str,
        sender_id: int,
        message: str,
    ) -> SupportMessage:
        cursor = self._connection.execute(
            """
            INSERT INTO support_messages (ticket_id, sender_type, sender_id, message)
            VALUES (?, ?, ?, ?)
            """,
            (ticket_id, sender_type, sender_id, message),
        )
        message_id = int(cursor.lastrowid)
        row = self._select_messages(message_id=message_id).fetchone()

        return _support_message_from_row(row)

    def list_support_messages(self, ticket_id: int) -> list[SupportMessage]:
        rows = self._select_messages(ticket_id=ticket_id).fetchall()
        return [_support_message_from_row(row) for row in rows]

    def _select_tickets(
        self,
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

        return self._connection.execute(
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

    def _select_messages(
        self,
        *,
        ticket_id: int | None = None,
        message_id: int | None = None,
    ) -> sqlite3.Cursor:
        where_parts: list[str] = []
        params: list[int] = []
        if ticket_id is not None:
            where_parts.append("ticket_id = ?")
            params.append(ticket_id)
        if message_id is not None:
            where_parts.append("id = ?")
            params.append(message_id)

        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

        return self._connection.execute(
            f"""
            SELECT id, ticket_id, sender_type, sender_id, message, created_at
            FROM support_messages
            {where_sql}
            ORDER BY created_at ASC, id ASC
            """,
            params,
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


def _support_message_from_row(row: sqlite3.Row) -> SupportMessage:
    return SupportMessage(
        id=int(row["id"]),
        ticket_id=int(row["ticket_id"]),
        sender_type=row["sender_type"],
        sender_id=int(row["sender_id"]),
        message=row["message"],
        created_at=row["created_at"],
    )
