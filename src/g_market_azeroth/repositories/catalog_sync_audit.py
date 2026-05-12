from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CatalogSyncAudit:
    id: int
    created_at: str
    admin_telegram_id: int
    created_count: int
    updated_count: int
    hidden_count: int
    error_count: int
    status: str


class CatalogSyncAuditRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def init_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS catalog_sync_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                admin_telegram_id INTEGER NOT NULL,
                created_count INTEGER NOT NULL,
                updated_count INTEGER NOT NULL,
                hidden_count INTEGER NOT NULL,
                error_count INTEGER NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_catalog_sync_audit_created_at
            ON catalog_sync_audit(created_at DESC)
            """
        )

    def create(
        self,
        *,
        admin_telegram_id: int,
        created_count: int,
        updated_count: int,
        hidden_count: int,
        error_count: int,
        status: str,
    ) -> CatalogSyncAudit:
        cursor = self._connection.execute(
            """
            INSERT INTO catalog_sync_audit (
                admin_telegram_id,
                created_count,
                updated_count,
                hidden_count,
                error_count,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                admin_telegram_id,
                created_count,
                updated_count,
                hidden_count,
                error_count,
                status,
            ),
        )
        row = self._select(int(cursor.lastrowid))
        return _audit_from_row(row)

    def latest(self, limit: int) -> list[CatalogSyncAudit]:
        rows = self._connection.execute(
            """
            SELECT id, created_at, admin_telegram_id, created_count, updated_count, hidden_count, error_count, status
            FROM catalog_sync_audit
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_audit_from_row(row) for row in rows]

    def _select(self, audit_id: int) -> sqlite3.Row:
        return self._connection.execute(
            """
            SELECT id, created_at, admin_telegram_id, created_count, updated_count, hidden_count, error_count, status
            FROM catalog_sync_audit
            WHERE id = ?
            """,
            (audit_id,),
        ).fetchone()


def _audit_from_row(row: sqlite3.Row) -> CatalogSyncAudit:
    return CatalogSyncAudit(
        id=int(row["id"]),
        created_at=row["created_at"],
        admin_telegram_id=int(row["admin_telegram_id"]),
        created_count=int(row["created_count"]),
        updated_count=int(row["updated_count"]),
        hidden_count=int(row["hidden_count"]),
        error_count=int(row["error_count"]),
        status=row["status"],
    )
