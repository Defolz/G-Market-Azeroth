import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv


@dataclass(slots=True)
class Settings:
    bot_token: str
    admin_ids: set[int]
    database_path: str
    log_level: str


# future:
# postgres_dsn
# redis_dsn
# webhook_base_url


def load_settings() -> Settings:
    load_dotenv(find_dotenv(usecwd=True))

    bot_token = _get_required_env("BOT_TOKEN")
    admin_ids = _parse_admin_ids(_get_required_env("ADMIN_IDS"))
    database_path = _get_required_env("DATABASE_PATH")
    log_level = _get_optional_env("LOG_LEVEL", default="INFO")

    return Settings(
        bot_token=bot_token,
        admin_ids=admin_ids,
        database_path=database_path,
        log_level=log_level,
    )


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"{name} is required. Add it to .env or environment variables.")

    value = value.strip()
    if not value:
        raise RuntimeError(f"{name} must not be empty.")

    return value


def _get_optional_env(name: str, *, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default

    value = value.strip()
    return value or default


def _parse_admin_ids(raw_value: str) -> set[int]:
    if not raw_value:
        raise RuntimeError("ADMIN_IDS must not be empty.")

    admin_ids: set[int] = set()
    for item in raw_value.split(","):
        value = item.strip()
        if not value:
            continue

        try:
            admin_ids.add(int(value))
        except ValueError as exc:
            raise RuntimeError("ADMIN_IDS must contain Telegram user IDs separated by commas.") from exc

    if not admin_ids:
        raise RuntimeError("ADMIN_IDS must contain at least one Telegram user ID.")

    return admin_ids
