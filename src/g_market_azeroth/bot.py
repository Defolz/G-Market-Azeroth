import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher

from g_market_azeroth import admin, handlers
from g_market_azeroth.config import load_settings
from g_market_azeroth.database import MarketRepository


async def run_bot() -> None:
    settings = load_settings()
    database = MarketRepository(Path(settings.database_path))
    await database.init()

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher(settings=settings, database=database)
    dispatcher.include_router(admin.router)
    dispatcher.include_router(handlers.router)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


def main() -> None:
    asyncio.run(run_bot())
