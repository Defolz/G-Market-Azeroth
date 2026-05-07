import asyncio
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from aiogram.types import Chat, ErrorEvent, Message, Update

from g_market_azeroth.error_handlers import FALLBACK_ERROR_MESSAGE, handle_error


def make_error_event(update: Update | None = None, exception: Exception | None = None) -> ErrorEvent:
    return ErrorEvent(
        update=update or Update(update_id=1),
        exception=exception or RuntimeError("boom"),
    )


def make_message_update() -> Update:
    return Update(
        update_id=1,
        message=Message(
            message_id=10,
            date=datetime.now(timezone.utc),
            chat=Chat(id=123456, type="private"),
            text="/start",
        ),
    )


def test_handle_error_logs_exception(caplog) -> None:
    exception = RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="g_market_azeroth.error_handlers"):
        asyncio.run(handle_error(make_error_event(exception=exception)))

    assert "Unhandled aiogram error" in caplog.text
    assert any(record.exc_info and record.exc_info[1] is exception for record in caplog.records)


def test_handle_error_sends_fallback_message_for_message(monkeypatch) -> None:
    answer = AsyncMock()
    monkeypatch.setattr(Message, "answer", answer)

    asyncio.run(handle_error(make_error_event(update=make_message_update())))

    answer.assert_awaited_once_with(FALLBACK_ERROR_MESSAGE)


def test_handle_error_does_not_raise_when_fallback_answer_fails(monkeypatch, caplog) -> None:
    async def fail_answer(self, text: str) -> None:
        raise RuntimeError("telegram send failed")

    monkeypatch.setattr(Message, "answer", fail_answer)

    with caplog.at_level(logging.WARNING, logger="g_market_azeroth.error_handlers"):
        asyncio.run(handle_error(make_error_event(update=make_message_update())))

    assert "Failed to send fallback error message to user." in caplog.text


def test_handle_error_ignores_update_without_message_or_callback(monkeypatch, caplog) -> None:
    answer = AsyncMock()
    monkeypatch.setattr(Message, "answer", answer)

    with caplog.at_level(logging.WARNING, logger="g_market_azeroth.error_handlers"):
        asyncio.run(handle_error(make_error_event(update=Update(update_id=1))))

    answer.assert_not_awaited()
    assert "Failed to send fallback error message to user." not in caplog.text
