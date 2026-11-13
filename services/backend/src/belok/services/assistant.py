"""AI assistant chats: Premium only, with per-user and global spend limits."""

import logging
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from belok.config import Settings
from belok.db.models import AiChat, AiMessage, LlmUsage, User
from belok.i18n import Language
from belok.llm.assistant import Assistant, AssistantError, Reply
from belok.services.access import AccessStatus, access_status
from belok.services.notify import notify_admins
from belok.services.repo import CHAT_KIND, REVIEW_KIND
from belok.services.snapshot import snapshot
from belok.timeutil import local_today, utcnow

log = logging.getLogger(__name__)

MAX_CHARS = 1000
HISTORY_MESSAGES = 16
PER_MINUTE = 5
REPLY_TOKENS = 3000
TITLE_CHARS = 60


class AssistantLimit(Exception):
    """code: premium_required, daily_limit, too_fast or assistant_busy."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def daily_messages(user: User, settings: Settings) -> int:
    if user.daily_limit is not None:
        return user.daily_limit
    if access_status(user, utcnow()) == AccessStatus.TRIAL:
        return settings.assistant_trial_messages
    return settings.assistant_daily_messages


async def messages_left(session: AsyncSession, user: User, settings: Settings) -> int:
    used = await session.scalar(
        select(func.count())
        .select_from(LlmUsage)
        .where(
            LlmUsage.user_id == user.id,
            LlmUsage.day == local_today(user.timezone),
            LlmUsage.kind == CHAT_KIND,
            LlmUsage.ok.is_(True),
        )
    )
    return max(0, daily_messages(user, settings) - used)


async def spent_today(session: AsyncSession) -> float:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    total = await session.scalar(
        select(func.coalesce(func.sum(LlmUsage.cost_usd), 0.0)).where(
            LlmUsage.created_at >= start, LlmUsage.kind.in_((CHAT_KIND, REVIEW_KIND))
        )
    )
    return float(total)


async def check_limits(session: AsyncSession, user: User, settings: Settings) -> None:
    if access_status(user, utcnow()) == AccessStatus.EXPIRED:
        raise AssistantLimit("premium_required")
    if await messages_left(session, user, settings) == 0:
        raise AssistantLimit("daily_limit")
    recent = await session.scalar(
        select(func.count())
        .select_from(LlmUsage)
        .where(
            LlmUsage.user_id == user.id,
            LlmUsage.kind == CHAT_KIND,
            LlmUsage.created_at > utcnow() - timedelta(minutes=1),
        )
    )
    if recent >= PER_MINUTE:
        raise AssistantLimit("too_fast")
    if await spent_today(session) >= settings.assistant_daily_budget_usd:
        raise AssistantLimit("assistant_busy")


def new_chat(user: User, text: str, kind: str = CHAT_KIND) -> AiChat:
    title = " ".join(text.split())
    if len(title) > TITLE_CHARS:
        title = title[: TITLE_CHARS - 1].rstrip() + "…"
    return AiChat(user_id=user.id, kind=kind, title=title, messages=[])


async def list_chats(session: AsyncSession, user_id: int) -> list[AiChat]:
    return list(
        await session.scalars(
            select(AiChat).where(AiChat.user_id == user_id).order_by(AiChat.updated_at.desc())
        )
    )


async def get_chat(session: AsyncSession, user_id: int, chat_id: int) -> AiChat | None:
    chat = await session.get(AiChat, chat_id)
    return chat if chat is not None and chat.user_id == user_id else None


def _history(chat: AiChat, text: str) -> list[dict]:
    history = [{"role": m.role, "content": m.text} for m in chat.messages[-HISTORY_MESSAGES:]]
    while history and history[0]["role"] != "user":
        history.pop(0)
    history.append({"role": "user", "content": text})
    return history


def usage_row(user: User, kind: str, model: str, reply: Reply | None, latency_ms: int) -> LlmUsage:
    return LlmUsage(
        user_id=user.id,
        day=local_today(user.timezone),
        kind=kind,
        model=model,
        prompt_tokens=reply.prompt_tokens if reply else 0,
        completion_tokens=reply.completion_tokens if reply else 0,
        cost_usd=reply.cost_usd if reply else None,
        latency_ms=latency_ms,
        ok=reply is not None,
    )


async def send_message(
    session: AsyncSession,
    bot: Bot | None,
    settings: Settings,
    assistant: Assistant,
    user: User,
    chat: AiChat,
    text: str,
) -> AiMessage:
    """Ask the assistant and store both messages; raises AssistantLimit or AssistantError."""
    await check_limits(session, user, settings)
    data = await snapshot(session, user, local_today(user.timezone))
    history = _history(chat, text)
    lang = user.language or Language.RU
    spent_before = await spent_today(session)
    # Return the DB connection to the pool while the model is thinking.
    await session.commit()
    try:
        reply = await assistant.chat(data, history, lang, REPLY_TOKENS)
    except AssistantError as exc:
        session.add(usage_row(user, CHAT_KIND, exc.model, None, exc.latency_ms))
        await session.commit()
        raise
    session.add(usage_row(user, CHAT_KIND, reply.model, reply, reply.latency_ms))
    now = utcnow()
    chat.messages.append(AiMessage(role="user", text=text, created_at=now))
    answer = AiMessage(role="assistant", text=reply.text, created_at=now)
    chat.messages.append(answer)
    chat.updated_at = now
    if chat.id is None:
        session.add(chat)
    await session.commit()
    await _alert_on_budget(session, bot, settings, spent_before, reply.cost_usd)
    return answer


async def _alert_on_budget(
    session: AsyncSession,
    bot: Bot | None,
    settings: Settings,
    before: float,
    cost: float | None,
) -> None:
    cap = settings.assistant_daily_budget_usd
    if bot is None or cost is None or not before < cap <= before + cost:
        return
    text = (
        f"🧠 AI-ассистент потратил сегодня ${before + cost:.2f} и упёрся в дневной лимит "
        f"${cap:.2f}. Чат на паузе до полуночи UTC, лимит: ASSISTANT_DAILY_BUDGET_USD."
    )
    try:
        await notify_admins(bot, session, "errors", text)
    except Exception:
        log.warning("failed to send the assistant budget alert", exc_info=True)
