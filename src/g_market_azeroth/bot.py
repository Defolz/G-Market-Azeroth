import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher

from g_market_azeroth import admin, error_handlers, handlers
from g_market_azeroth.config import load_settings
from g_market_azeroth.database import MarketRepository
from g_market_azeroth.logging import setup_logging


async def run_bot() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)

    database = MarketRepository(Path(settings.database_path))
    await database.init()

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher(settings=settings, database=database)
    dispatcher.errors.register(error_handlers.handle_error)
    dispatcher.include_router(admin.router)
    dispatcher.include_router(handlers.router)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


def main() -> None:
    asyncio.run(run_bot())
