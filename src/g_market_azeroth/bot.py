import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher

from g_market_azeroth import admin, error_handlers, handlers
from g_market_azeroth.config import load_settings
from g_market_azeroth.database import MarketRepository
from g_market_azeroth.logging import setup_logging
from g_market_azeroth.middlewares.rate_limit import (
    SupportCooldownMiddleware,
    UserCooldownMiddleware,
)


async def run_bot() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)

    database = MarketRepository(Path(settings.database_path))
    await database.init()

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher(settings=settings, database=database)
    dispatcher.message.middleware(
        UserCooldownMiddleware(
            cooldown_seconds=settings.message_cooldown_seconds,
            skip_when_state_set=True,
        )
    )
    dispatcher.message.middleware(
        SupportCooldownMiddleware(cooldown_seconds=settings.support_cooldown_seconds)
    )
    dispatcher.callback_query.middleware(
        UserCooldownMiddleware(
            cooldown_seconds=settings.callback_cooldown_seconds,
            answer_callbacks=True,
        )
    )
    dispatcher.errors.register(error_handlers.handle_error)
    dispatcher.include_router(admin.router)
    dispatcher.include_router(handlers.router)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


def main() -> None:
    asyncio.run(run_bot())
