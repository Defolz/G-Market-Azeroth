from __future__ import annotations

import logging


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_APP_HANDLER_MARKER = "_g_market_azeroth_handler"


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


def _parse_log_level(log_level: str) -> int:
    level_name = log_level.strip().upper()
    level = logging.getLevelName(level_name)
    if isinstance(level, int):
        return level

    return logging.INFO
