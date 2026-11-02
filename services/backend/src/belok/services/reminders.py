import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from redis.asyncio import Redis
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from belok.bot.texts import t
from belok.db.models import BodyWeight, Meal, User
from belok.i18n import Language
from belok.services.access import has_access
from belok.timeutil import utcnow

log = logging.getLogger(__name__)

CHECK_INTERVAL = 300
SEND_WINDOW = timedelta(hours=1)
# Users who haven't opened the app for this long stop getting reminders.
ACTIVE_WITHIN = timedelta(days=14)
WEIGH_IN_GAP_DAYS = 3


class Reminder(StrEnum):
    WEIGHT = "weight"
    LUNCH = "lunch"
    DINNER = "dinner"


SCHEDULE = {
    Reminder.WEIGHT: time(8, 30),
    Reminder.LUNCH: time(14, 0),
    Reminder.DINNER: time(20, 30),
}
# A meal logged after this local time counts as the one the reminder asks about.
MEAL_SINCE = {Reminder.LUNCH: time(11, 0), Reminder.DINNER: time(17, 0)}

Claim = Callable[[str], Awaitable[bool]]


def due(local_now: datetime) -> list[Reminder]:
    result = []
    for kind, at in SCHEDULE.items():
        start = local_now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
        if start <= local_now < start + SEND_WINDOW:
            result.append(kind)
    return result


def enabled(user: User, kind: Reminder) -> bool:
    return user.remind_weight if kind == Reminder.WEIGHT else user.remind_meals


async def run_reminders(
    bot: Bot, sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, webapp_url: str | None
) -> None:
    async def claim(key: str) -> bool:
        return bool(await redis.set(key, 1, nx=True, ex=2 * 86400))

    while True:
        try:
            async with sessionmaker() as session:
                await send_due(bot, session, claim, webapp_url, utcnow())
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("reminders failed")
        await asyncio.sleep(CHECK_INTERVAL)


async def send_due(
    bot: Bot, session: AsyncSession, claim: Claim, webapp_url: str | None, now: datetime
) -> int:
    users = await session.scalars(
        select(User).where(
            or_(User.remind_meals.is_(True), User.remind_weight.is_(True)),
            User.bot_blocked.is_(False),
            User.is_blocked.is_(False),
            User.last_seen_at >= now - ACTIVE_WITHIN,
            User.sex.is_not(None),
            User.birth_year.is_not(None),
            User.height_cm.is_not(None),
            User.goal.is_not(None),
        )
    )
    sent = 0
    for user in users.all():
        if not has_access(user, now):
            continue
        local = now.astimezone(ZoneInfo(user.timezone))
        for kind in due(local):
            if not enabled(user, kind):
                continue
            key = await _message_key(session, user, kind, local)
            if key is None or not await claim(f"belok:remind:{kind}:{user.id}:{local.date()}"):
                continue
            if await _send(bot, user, kind, key, webapp_url):
                sent += 1
    await session.commit()
    return sent


async def _message_key(
    session: AsyncSession, user: User, kind: Reminder, local: datetime
) -> str | None:
    """Text key of the reminder to send, or None when the user has already logged it."""
    if kind == Reminder.WEIGHT:
        last = await session.scalar(
            select(func.max(BodyWeight.day)).where(BodyWeight.user_id == user.id)
        )
        if last is not None and (local.date() - last).days < WEIGH_IN_GAP_DAYS:
            return None
        return "remind_weight"

    since = datetime.combine(local.date(), MEAL_SINCE[kind], local.tzinfo)
    today, recent = (
        await session.execute(
            select(func.count(), func.count().filter(Meal.created_at >= since)).where(
                Meal.user_id == user.id, Meal.day == local.date()
            )
        )
    ).one()
    if recent:
        return None
    if not today:
        return "remind_nothing_today"
    return f"remind_{kind}"


async def _send(bot: Bot, user: User, kind: Reminder, key: str, webapp_url: str | None) -> bool:
    lang = user.language or Language.RU
    pref = "weight" if kind == Reminder.WEIGHT else "meals"
    buttons = []
    if webapp_url:
        path, label = ("weight", "log_weight") if kind == Reminder.WEIGHT else ("add", "log_meal")
        url = f"{webapp_url.rstrip('/')}/{path}"
        buttons.append([InlineKeyboardButton(text=t(lang, label), web_app=WebAppInfo(url=url))])
    buttons.append(
        [InlineKeyboardButton(text=t(lang, "remind_stop"), callback_data=f"remind_off:{pref}")]
    )
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    for _ in range(2):
        try:
            await bot.send_message(user.id, t(lang, key), reply_markup=markup)
            return True
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
        except TelegramForbiddenError:
            user.bot_blocked = True
            return False
        except TelegramAPIError:
            log.warning("reminder to %s failed", user.id, exc_info=True)
            return False
    return False
