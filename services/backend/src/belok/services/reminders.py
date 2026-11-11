import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from redis.asyncio import Redis
from sqlalchemy import Date, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from belok.bot.texts import t
from belok.db.models import BodyWeight, Meal, User
from belok.i18n import Language
from belok.services import features, heartbeat, widgets
from belok.services.features import Feature
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

# Meal reminders follow the user's usual meal time once there is enough history.
LEARN_DAYS = 28
MIN_DAYS = 5
GRACE = timedelta(minutes=45)
MEAL_BOUNDS = {
    Reminder.LUNCH: (time(12, 30), time(16, 0)),
    Reminder.DINNER: (time(18, 0), time(22, 30)),
}

Claim = Callable[[str], Awaitable[bool]]


def due(local_now: datetime, schedule: Mapping[Reminder, time] = SCHEDULE) -> list[Reminder]:
    result = []
    for kind, at in schedule.items():
        start = local_now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
        if start <= local_now < start + SEND_WINDOW:
            result.append(kind)
    return result


def personal_schedule(usual: Mapping[Reminder, float]) -> dict[Reminder, time]:
    """Fixed schedule with meal slots moved to the usual meal minute plus a grace period."""
    schedule = dict(SCHEDULE)
    for kind, minute in usual.items():
        low, high = MEAL_BOUNDS[kind]
        at = round((minute + GRACE.total_seconds() / 60) / 5) * 5
        at = min(max(at, low.hour * 60 + low.minute), high.hour * 60 + high.minute)
        schedule[kind] = time(at // 60, at % 60)
    return schedule


async def usual_meal_minutes(
    session: AsyncSession, user_ids: Sequence[int], today: date
) -> dict[int, dict[Reminder, float]]:
    """Median local minute of the first lunch and dinner log per user, given enough days."""
    if not user_ids:
        return {}
    local = func.timezone(User.timezone, Meal.created_at)
    minute = func.extract("hour", local) * 60 + func.extract("minute", local)
    lunch, dinner = (t.hour * 60 + t.minute for t in MEAL_SINCE.values())
    slot = case((minute >= dinner, Reminder.DINNER.value), (minute >= lunch, Reminder.LUNCH.value))
    first = (
        select(Meal.user_id, slot.label("slot"), func.min(minute).label("minute"))
        .join(User, User.id == Meal.user_id)
        .where(
            Meal.user_id.in_(user_ids),
            Meal.day >= today - timedelta(days=LEARN_DAYS),
            cast(local, Date) == Meal.day,
            slot.is_not(None),
        )
        .group_by(Meal.user_id, Meal.day, slot)
        .subquery()
    )
    rows = await session.execute(
        select(
            first.c.user_id,
            first.c.slot,
            func.percentile_cont(0.5).within_group(first.c.minute),
        )
        .group_by(first.c.user_id, first.c.slot)
        .having(func.count() >= MIN_DAYS)
    )
    result: dict[int, dict[Reminder, float]] = {}
    for user_id, kind, median in rows:
        result.setdefault(user_id, {})[Reminder(kind)] = float(median)
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
                if await features.enabled(session, Feature.REMINDERS):
                    await send_due(bot, session, claim, webapp_url, utcnow())
                await heartbeat.beat(session, "reminders")
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("reminders failed")
        await asyncio.sleep(CHECK_INTERVAL)


async def send_due(
    bot: Bot, session: AsyncSession, claim: Claim, webapp_url: str | None, now: datetime
) -> int:
    candidates = await session.scalars(
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
    users = candidates.all()
    usual = await usual_meal_minutes(session, [u.id for u in users if u.remind_meals], now.date())
    sent = 0
    for user in users:
        local = now.astimezone(ZoneInfo(user.timezone))
        for kind in due(local, personal_schedule(usual.get(user.id, {}))):
            if not enabled(user, kind):
                continue
            key = await _message_key(session, user, kind, local)
            if key is None or not await claim(f"belok:remind:{kind}:{user.id}:{local.date()}"):
                continue
            widget = await _widget(session, user, kind, local)
            if await _send(bot, user, kind, key, webapp_url, widget):
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


async def _widget(
    session: AsyncSession, user: User, kind: Reminder, local: datetime
) -> tuple[str, str] | None:
    """Widget name and state for a one-tap reminder, or None to send plain text."""
    if not await widgets.enabled(session):
        return None
    if kind == Reminder.WEIGHT:
        return "weight", await widgets.weight_state(session, user)
    since = MEAL_SINCE[kind]
    until = MEAL_SINCE[Reminder.DINNER] if kind == Reminder.LUNCH else time(23, 59)
    meals = await widgets.usual_meals(session, user, since, until, local.date())
    return ("usual", widgets.usual_state(user, meals)) if meals else None


async def _send(
    bot: Bot,
    user: User,
    kind: Reminder,
    key: str,
    webapp_url: str | None,
    widget: tuple[str, str] | None = None,
) -> bool:
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
            if widget is not None:
                try:
                    await widgets.send(bot, user, *widget, t(lang, key), markup)
                    return True
                except TelegramBadRequest:
                    log.warning("reminder widget to %s failed", user.id, exc_info=True)
                    widget = None
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
