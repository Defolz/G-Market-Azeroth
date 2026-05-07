from __future__ import annotations

import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from g_market_azeroth.config import load_settings


def main() -> None:
    try:
        settings = load_settings()
        _check_bot_token(settings.bot_token)
        _check_database(settings.database_path)
    except Exception as exc:
        print(f"unhealthy: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("healthy")


def _check_bot_token(bot_token: str) -> None:
    if not bot_token.strip():
        raise RuntimeError("BOT_TOKEN must not be empty.")


def _check_database(database_path: str) -> None:
    path = Path(database_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(path)) as connection:
        connection.execute("SELECT 1").fetchone()


if __name__ == "__main__":
    main()
