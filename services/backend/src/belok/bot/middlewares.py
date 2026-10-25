from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from belok.bot import texts
from belok.db.models import User
from belok.services.access import has_access
from belok.services.users import get_or_create_user
from belok.timeutil import utcnow

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        async with self._sessionmaker() as session:
            data["session"] = session
            result = await handler(event, data)
            await session.commit()
            return result


class UserMiddleware(BaseMiddleware):
    def __init__(self, trial_days: int, default_timezone: str) -> None:
        self._trial_days = trial_days
        self._timezone = default_timezone

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        data["user"] = await get_or_create_user(
            data["session"], tg_user.id, tg_user.username, self._trial_days, self._timezone
        )
        return await handler(event, data)


class RequireActiveUser(BaseMiddleware):
    """Blocks handlers until the profile is filled in and the trial or subscription is active."""

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user: User | None = data.get("user")
        if user is None:
            return None
        if not user.profile_complete:
            return await _reply(event, texts.PROFILE_REQUIRED)
        if not has_access(user, utcnow()):
            return await _reply(event, texts.ACCESS_EXPIRED)
        return await handler(event, data)


async def _reply(event: TelegramObject, text: str) -> None:
    if isinstance(event, Message):
        await event.answer(text)
    elif isinstance(event, CallbackQuery):
        await event.answer(text, show_alert=True)
