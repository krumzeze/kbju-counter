import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import User

log = logging.getLogger(__name__)

DEFAULT_PREFS = {"new_users": True, "payments": True, "errors": True, "daily": True}


def admin_prefs(user: User) -> dict[str, bool]:
    return DEFAULT_PREFS | (user.admin_prefs or {})


async def admin_recipients(
    session: AsyncSession, pref: str, exclude: int | None = None
) -> list[int]:
    admins = await session.scalars(
        select(User).where(User.is_admin.is_(True), User.bot_blocked.is_(False))
    )
    return [a.id for a in admins if admin_prefs(a)[pref] and a.id != exclude]


async def send_all(bot: Bot, chat_ids: list[int], text: str) -> None:
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, text)
        except TelegramAPIError:
            log.warning("failed to notify admin %s", chat_id, exc_info=True)


async def notify_admins(
    bot: Bot, session: AsyncSession, pref: str, text: str, exclude: int | None = None
) -> None:
    await send_all(bot, await admin_recipients(session, pref, exclude), text)
