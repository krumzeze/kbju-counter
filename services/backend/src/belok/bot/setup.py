import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import BaseStorage
from aiogram.types import ErrorEvent
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from belok.bot.handlers import clarify, payments, reminders, start, support, voice
from belok.bot.middlewares import DbSessionMiddleware, UserMiddleware, WidgetQueryMiddleware
from belok.config import Settings
from belok.services import errors

log = logging.getLogger(__name__)


def build_dispatcher(
    settings: Settings, storage: BaseStorage, sessionmaker: async_sessionmaker[AsyncSession]
) -> Dispatcher:
    dp = Dispatcher(storage=storage)
    dp.update.outer_middleware(DbSessionMiddleware(sessionmaker))
    dp.update.outer_middleware(WidgetQueryMiddleware())
    dp.update.outer_middleware(UserMiddleware(settings))
    dp.include_router(payments.router)
    dp.include_router(support.router)
    dp.include_router(reminders.router)
    dp.include_router(clarify.router)
    dp.include_router(voice.router)
    dp.include_router(start.router)

    @dp.errors()
    async def on_error(event: ErrorEvent, bot: Bot) -> bool:
        log.error("update %s failed", event.update.update_id, exc_info=event.exception)
        update = event.update.event
        user = getattr(update, "from_user", None)
        await errors.capture(
            sessionmaker,
            bot,
            event.exception,
            "bot",
            path=event.update.event_type,
            user_id=user.id if user else None,
        )
        return True

    return dp
