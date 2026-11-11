from collections.abc import Awaitable, Callable
from html import escape
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from belok.bot import texts
from belok.config import Settings
from belok.db.models import User
from belok.i18n import guess_language
from belok.services.notify import notify_admins
from belok.services.users import get_or_create_user
from belok.services.widgets import answer_query
from belok.widgets.api import WidgetQuery

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


class WidgetQueryMiddleware(BaseMiddleware):
    """Handles widget_query updates, which aiogram does not route to handlers yet."""

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        raw = (event.model_extra or {}).get("widget_query") if isinstance(event, Update) else None
        if not isinstance(raw, dict):
            return await handler(event, data)
        query = WidgetQuery.parse(raw)
        session: AsyncSession = data["session"]
        user = await session.get(User, query.from_user.id)
        await answer_query(data["bot"], session, user, query)
        return None


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
        data["lang"] = user.language or guess_language(tg_user.language_code)
        if created:
            await _announce(data["bot"], session, user)
        if user.is_blocked:
            if isinstance(event, Update) and event.message:
                await event.message.answer(texts.t(data["lang"], "blocked"))
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
