import asyncio
import contextlib
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import MenuButtonWebApp, WebAppInfo
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from belok.bot.setup import COMMANDS, build_dispatcher
from belok.config import Settings
from belok.llm.analyzer import FoodAnalyzer
from belok.services.broadcasts import run_worker
from belok.services.monitor import run_monitor


async def main() -> None:
    settings = Settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    storage = RedisStorage.from_url(settings.redis_url)
    analyzer = FoodAnalyzer(settings.llm_api_key.get_secret_value(), settings.llm_model)
    bot = Bot(
        settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher(settings, storage, sessionmaker)
    background = [
        asyncio.create_task(run_worker(bot, sessionmaker)),
        asyncio.create_task(
            run_monitor(bot, sessionmaker, storage.redis, settings.default_timezone)
        ),
    ]

    try:
        await bot.set_my_commands(COMMANDS)
        if settings.webapp_url:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Открыть", web_app=WebAppInfo(url=settings.webapp_url)
                )
            )
        await dp.start_polling(bot, settings=settings, analyzer=analyzer)
    finally:
        for task in background:
            task.cancel()
        for task in background:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await storage.close()
        await engine.dispose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
