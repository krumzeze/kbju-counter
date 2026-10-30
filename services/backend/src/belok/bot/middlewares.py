from collections.abc import Awaitable, Callable
from html import escape
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from belok.bot import texts
from belok.config import Settings
from belok.db.models import User
from belok.services.access import has_access
from belok.services.notify import notify_admins
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
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        session: AsyncSession = data["session"]
        user, created = await get_or_create_user(
            session,
            self._settings,
            tg_user.id,
            tg_user.username,
            tg_user.first_name,
            _start_param(event),
        )
        user.bot_blocked = False
        data["user"] = user
        if created:
            await _announce(data["bot"], session, user)
        if user.is_blocked:
            if isinstance(event, Update) and event.message:
                await event.message.answer(texts.BLOCKED)
            return None
        return await handler(event, data)


def _start_param(event: TelegramObject) -> str | None:
    if not isinstance(event, Update) or event.message is None or event.message.text is None:
        return None
    command, _, arg = event.message.text.partition(" ")
    if command != "/start":
        return None
    return arg.strip() or None


async def _announce(bot: Bot, session: AsyncSession, user: User) -> None:
    name = f"@{user.username}" if user.username else escape(user.first_name or str(user.id))
    source = f"\nИсточник: {escape(user.source)}" if user.source else ""
    await notify_admins(
        bot, session, "new_users", f"👤 Новый пользователь: {name}{source}", exclude=user.id
    )


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
