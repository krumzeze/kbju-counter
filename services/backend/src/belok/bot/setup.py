from aiogram import Dispatcher, Router
from aiogram.fsm.storage.base import BaseStorage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from belok.bot.handlers import admin, meals, start, tracking, workouts
from belok.bot.middlewares import DbSessionMiddleware, RequireActiveUser, UserMiddleware
from belok.config import Settings


def build_dispatcher(
    settings: Settings, storage: BaseStorage, sessionmaker: async_sessionmaker[AsyncSession]
) -> Dispatcher:
    dp = Dispatcher(storage=storage)
    dp.update.outer_middleware(DbSessionMiddleware(sessionmaker))
    dp.update.outer_middleware(UserMiddleware(settings))

    gated = Router(name="gated")
    gated.message.middleware(RequireActiveUser())
    gated.callback_query.middleware(RequireActiveUser())
    # meals goes last: it catches any free text as a meal description.
    gated.include_routers(tracking.router, workouts.router, meals.router)

    dp.include_routers(start.router, admin.router, gated)
    return dp
