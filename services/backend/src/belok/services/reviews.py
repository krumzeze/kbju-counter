"""Weekly AI review: one insight and one tip, written on Monday for Premium users."""

import asyncio
import logging
from datetime import date, datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from belok.bot.texts import t
from belok.config import Settings
from belok.db.models import AiChat, AiMessage, Meal, User
from belok.i18n import Language
from belok.llm.assistant import Assistant, AssistantError
from belok.services import features, heartbeat
from belok.services.assistant import spent_today, usage_row
from belok.services.features import Feature
from belok.services.repo import REVIEW_KIND
from belok.services.snapshot import snapshot
from belok.timeutil import utcnow

log = logging.getLogger(__name__)

CHECK_INTERVAL = 900
SEND_AFTER = time(10, 0)
ACTIVE_WITHIN = timedelta(days=14)
MIN_LOGGED_DAYS = 3
PER_RUN = 20
PREVIEW_CHARS = 300


def week_start(local_day: date) -> date:
    return local_day - timedelta(days=local_day.weekday())


def is_due(local: datetime) -> bool:
    return local.weekday() == 0 and local.time() >= SEND_AFTER


def review_title(lang: Language, monday: date) -> str:
    start, end = monday - timedelta(days=7), monday - timedelta(days=1)
    return t(lang, "review_title", start=start.strftime("%d.%m"), end=end.strftime("%d.%m"))


async def _logged_days(session: AsyncSession, user_id: int, start: date, end: date) -> int:
    return await session.scalar(
        select(func.count(func.distinct(Meal.day))).where(
            Meal.user_id == user_id, Meal.day >= start, Meal.day < end
        )
    )


async def _has_review(session: AsyncSession, user_id: int, since: datetime) -> bool:
    found = await session.scalar(
        select(AiChat.id).where(
            AiChat.user_id == user_id, AiChat.kind == REVIEW_KIND, AiChat.created_at >= since
        )
    )
    return found is not None


async def write_due(
    bot: Bot,
    session: AsyncSession,
    assistant: Assistant,
    settings: Settings,
    now: datetime,
) -> int:
    """Write and announce reviews for users whose Monday morning has come; returns how many."""
    users = await session.scalars(
        select(User).where(
            User.is_blocked.is_(False),
            User.bot_blocked.is_(False),
            User.last_seen_at >= now - ACTIVE_WITHIN,
            or_(
                User.lifetime_access.is_(True),
                User.subscription_until > now,
                User.trial_ends_at > now,
            ),
        )
    )
    written = 0
    for user in users.all():
        if written >= PER_RUN:
            break
        tz = ZoneInfo(user.timezone)
        local = now.astimezone(tz)
        if not is_due(local):
            continue
        monday = week_start(local.date())
        since = datetime.combine(monday, time(0), tz)
        if await _has_review(session, user.id, since):
            continue
        logged = await _logged_days(session, user.id, monday - timedelta(days=7), monday)
        if logged < MIN_LOGGED_DAYS:
            continue
        if await spent_today(session) >= settings.assistant_daily_budget_usd:
            log.warning("assistant budget reached, weekly reviews postponed")
            break
        if await write_review(bot, session, assistant, settings, user, monday, now):
            written += 1
    return written


async def write_review(
    bot: Bot,
    session: AsyncSession,
    assistant: Assistant,
    settings: Settings,
    user: User,
    monday: date,
    now: datetime,
) -> bool:
    lang = user.language or Language.RU
    data = await snapshot(session, user, monday)
    await session.commit()
    try:
        reply = await assistant.review(data, lang)
    except AssistantError as exc:
        session.add(usage_row(user, REVIEW_KIND, exc.model, None, exc.latency_ms))
        await session.commit()
        log.warning("weekly review for %s failed", user.id, exc_info=True)
        return False
    session.add(usage_row(user, REVIEW_KIND, reply.model, reply, reply.latency_ms))
    chat = AiChat(
        user_id=user.id,
        kind=REVIEW_KIND,
        title=review_title(lang, monday),
        created_at=now,
        updated_at=now,
        messages=[AiMessage(role="assistant", text=reply.text, created_at=now)],
    )
    session.add(chat)
    await session.commit()
    await _announce(bot, user, lang, chat, reply.text, settings.webapp_url)
    await session.commit()
    return True


async def _announce(
    bot: Bot, user: User, lang: Language, chat: AiChat, text: str, webapp_url: str | None
) -> None:
    preview = text if len(text) <= PREVIEW_CHARS else text[: PREVIEW_CHARS - 1].rstrip() + "…"
    markup = None
    if webapp_url:
        url = f"{webapp_url.rstrip('/')}/assistant/{chat.id}"
        button = InlineKeyboardButton(text=t(lang, "review_open"), web_app=WebAppInfo(url=url))
        markup = InlineKeyboardMarkup(inline_keyboard=[[button]])
    try:
        await bot.send_message(
            user.id, t(lang, "review_ready", text=escape(preview)), reply_markup=markup
        )
    except TelegramForbiddenError:
        user.bot_blocked = True
    except TelegramAPIError:
        log.warning("weekly review message to %s failed", user.id, exc_info=True)


async def run_reviews(
    bot: Bot, sessionmaker: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    assistant = Assistant(
        settings.llm_api_key.get_secret_value(), settings.assistant_model, settings.review_model
    )
    while True:
        try:
            async with sessionmaker() as session:
                if await features.enabled(session, Feature.ASSISTANT):
                    await write_due(bot, session, assistant, settings, utcnow())
                await heartbeat.beat(session, "reviews")
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("weekly reviews failed")
        await asyncio.sleep(CHECK_INTERVAL)
