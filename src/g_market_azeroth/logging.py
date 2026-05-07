from __future__ import annotations

import logging
from typing import Any


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_APP_HANDLER_MARKER = "_g_market_azeroth_handler"
_AUDIT_LOGGER_NAME = "g_market_azeroth.audit"


def setup_logging(log_level: str) -> None:
    level = _parse_log_level(log_level)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    root_logger = logging.getLogger()

    root_logger.setLevel(level)

    for handler in root_logger.handlers:
        if getattr(handler, _APP_HANDLER_MARKER, False):
            handler.setFormatter(formatter)
            handler.setLevel(logging.NOTSET)
            return

    if root_logger.handlers:
        for handler in root_logger.handlers:
            handler.setFormatter(formatter)
            handler.setLevel(logging.NOTSET)
        return

    handler = logging.StreamHandler()
    setattr(handler, _APP_HANDLER_MARKER, True)
    handler.setFormatter(formatter)
    handler.setLevel(logging.NOTSET)
    root_logger.addHandler(handler)


def log_admin_action(admin_id: int, action: str, **fields: Any) -> None:
    _log_audit_event("ADMIN_ACTION", actor_field="admin_id", actor_id=admin_id, action=action, fields=fields)


def log_user_action(user_id: int, action: str, **fields: Any) -> None:
    _log_audit_event("USER_ACTION", actor_field="user_id", actor_id=user_id, action=action, fields=fields)


def _parse_log_level(log_level: str) -> int:
    level_name = log_level.strip().upper()
    level = logging.getLevelName(level_name)
    if isinstance(level, int):
        return level

    return logging.INFO


def _log_audit_event(
    event_type: str,
    *,
    actor_field: str,
    actor_id: int,
    action: str,
    fields: dict[str, Any],
) -> None:
    parts = [
        event_type,
        f"{actor_field}={actor_id}",
        f"action={_audit_value(action)}",
    ]
    for key, value in fields.items():
        if value is None:
            continue
        parts.append(f"{key}={_audit_value(value)}")

    logging.getLogger(_AUDIT_LOGGER_NAME).info(" | ".join(parts))


def _audit_value(value: Any) -> str:
    return str(value).replace("|", "/").replace("\r", " ").replace("\n", " ").strip()
