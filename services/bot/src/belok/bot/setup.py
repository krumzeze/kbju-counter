from aiogram import Dispatcher, Router
from aiogram.fsm.storage.base import BaseStorage
from aiogram.types import BotCommand
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from belok.bot.handlers import meals, start, tracking, workouts
from belok.bot.middlewares import DbSessionMiddleware, RequireActiveUser, UserMiddleware
from belok.config import Settings

COMMANDS = [
    BotCommand(command="today", description="Итоги дня"),
    BotCommand(command="weight", description="Записать вес"),
    BotCommand(command="steps", description="Записать шаги"),
    BotCommand(command="gym", description="Записать подходы"),
    BotCommand(command="progress", description="Прогресс по упражнению"),
    BotCommand(command="profile", description="Изменить анкету"),
    BotCommand(command="help", description="Помощь"),
]


def build_dispatcher(
    settings: Settings, storage: BaseStorage, sessionmaker: async_sessionmaker[AsyncSession]
) -> Dispatcher:
    dp = Dispatcher(storage=storage)
    dp.update.outer_middleware(DbSessionMiddleware(sessionmaker))
    dp.update.outer_middleware(UserMiddleware(settings.trial_days, settings.default_timezone))

    gated = Router(name="gated")
    gated.message.middleware(RequireActiveUser())
    gated.callback_query.middleware(RequireActiveUser())
    # meals goes last: it catches any free text as a meal description.
    gated.include_routers(tracking.router, workouts.router, meals.router)

    dp.include_routers(start.router, gated)
    return dp
