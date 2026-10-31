from aiogram import Dispatcher
from aiogram.fsm.storage.base import BaseStorage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from belok.bot.handlers import start
from belok.bot.middlewares import DbSessionMiddleware, UserMiddleware
from belok.config import Settings


def build_dispatcher(
    settings: Settings, storage: BaseStorage, sessionmaker: async_sessionmaker[AsyncSession]
) -> Dispatcher:
    dp = Dispatcher(storage=storage)
    dp.update.outer_middleware(DbSessionMiddleware(sessionmaker))
    dp.update.outer_middleware(UserMiddleware(settings))
    dp.include_router(start.router)
    return dp
