import logging

from aiogram.types import CallbackQuery, ErrorEvent, Message


FALLBACK_ERROR_MESSAGE = "Произошла ошибка. Попробуйте ещё раз или напишите в поддержку."

logger = logging.getLogger(__name__)


async def handle_error(event: ErrorEvent) -> None:
    logger.exception(
        "Unhandled aiogram error",
        exc_info=(
            type(event.exception),
            event.exception,
            event.exception.__traceback__,
        ),
    )

    try:
        await _notify_user(event)
    except Exception:
        logger.warning("Failed to send fallback error message to user.", exc_info=True)


async def _notify_user(event: ErrorEvent) -> None:
    message = event.update.message
    if isinstance(message, Message):
        await message.answer(FALLBACK_ERROR_MESSAGE)
        return

    callback = event.update.callback_query
    if isinstance(callback, CallbackQuery):
        await callback.answer(FALLBACK_ERROR_MESSAGE, show_alert=True)
