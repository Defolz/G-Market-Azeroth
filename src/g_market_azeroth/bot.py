import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from g_market_azeroth.config import Settings


async def handle_start(message: Message) -> None:
    await message.answer("Привет!")


async def run_bot() -> None:
    settings = Settings.from_env()

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.message.register(handle_start, CommandStart())

    await dispatcher.start_polling(bot)


def main() -> None:
    asyncio.run(run_bot())
