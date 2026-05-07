from __future__ import annotations

import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path

from g_market_azeroth.config import load_settings


BACKUP_DIR = Path("backups")
BACKUP_KEEP_COUNT = 10


def main() -> None:
    try:
        backup_path = create_backup()
    except Exception as exc:
        print(f"backup failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"backup created: {backup_path}")


def create_backup() -> Path:
    settings = load_settings()
    source_path = Path(settings.database_path)
    if not source_path.exists():
        raise RuntimeError(f"SQLite database not found: {source_path}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = _backup_path(source_path)

    with closing(sqlite3.connect(source_path)) as source:
        with closing(sqlite3.connect(backup_path)) as destination:
            source.backup(destination)

    _prune_backups(source_path.stem)
    return backup_path


def _backup_path(source_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return BACKUP_DIR / f"{source_path.stem}-{timestamp}{source_path.suffix}"


def _prune_backups(source_stem: str) -> None:
    backups = sorted(
        BACKUP_DIR.glob(f"{source_stem}-*.sqlite3"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for backup_path in backups[BACKUP_KEEP_COUNT:]:
        backup_path.unlink()


if __name__ == "__main__":
    main()
