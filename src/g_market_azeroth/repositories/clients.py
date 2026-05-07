from __future__ import annotations

import sqlite3
from dataclasses import dataclass


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


class ClientsRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def init_schema(self) -> None:
        self._connection.execute(
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
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_clients_last_seen_at
            ON clients(last_seen_at DESC)
            """
        )

    def upsert_client(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None,
        is_bot: bool,
    ) -> None:
        self._connection.execute(
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

    def get_client(self, telegram_id: int) -> Client | None:
        row = self._select_client(telegram_id)
        return _client_from_row(row) if row else None

    def count_clients(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) AS count FROM clients").fetchone()
        return int(row["count"])

    def latest_clients(self, limit: int) -> list[Client]:
        rows = self._connection.execute(
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

    def _select_client(self, telegram_id: int) -> sqlite3.Row | None:
        return self._connection.execute(
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
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        ).fetchone()


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
