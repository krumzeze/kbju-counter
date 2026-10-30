import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from belok.db.models import Broadcast, User
from belok.services.admin_users import Segment, segment_filter
from belok.timeutil import utcnow

log = logging.getLogger(__name__)

# Telegram allows about 30 messages per second to different chats.
BATCH_SIZE = 25
BATCH_INTERVAL = 1.0
POLL_INTERVAL = 3.0


async def segment_size(session: AsyncSession, segment: Segment) -> int:
    return await session.scalar(
        select(func.count()).select_from(User).where(*segment_filter(segment, utcnow()))
    )


async def run_worker(bot: Bot, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    """Delivers broadcasts in the `sending` state. Progress is stored after every batch,
    so a restart resumes where it stopped."""
    while True:
        try:
            if not await _step(bot, sessionmaker):
                await asyncio.sleep(POLL_INTERVAL)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("broadcast worker failed")
            await asyncio.sleep(POLL_INTERVAL)


async def _step(bot: Bot, sessionmaker: async_sessionmaker[AsyncSession]) -> bool:
    async with sessionmaker() as session:
        broadcast = await session.scalar(
            select(Broadcast).where(Broadcast.status == "sending").order_by(Broadcast.id).limit(1)
        )
        if broadcast is None:
            return False
        recipients = list(
            await session.scalars(
                select(User.id)
                .where(
                    User.id > broadcast.cursor,
                    *segment_filter(Segment(broadcast.segment), utcnow()),
                )
                .order_by(User.id)
                .limit(BATCH_SIZE)
            )
        )
        if not recipients:
            broadcast.status = "done"
            broadcast.finished_at = utcnow()
            await session.commit()
            return True

        blocked: list[int] = []
        for chat_id in recipients:
            result = await _deliver(bot, chat_id, broadcast.text)
            if result == "sent":
                broadcast.sent += 1
            elif result == "blocked":
                broadcast.blocked += 1
                blocked.append(chat_id)
            else:
                broadcast.failed += 1
        broadcast.cursor = recipients[-1]
        if blocked:
            await session.execute(update(User).where(User.id.in_(blocked)).values(bot_blocked=True))
        await session.commit()
    await asyncio.sleep(BATCH_INTERVAL)
    return True


async def _deliver(bot: Bot, chat_id: int, text: str) -> str:
    for _ in range(3):
        try:
            await bot.send_message(chat_id, text)
            return "sent"
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
        except TelegramForbiddenError:
            return "blocked"
        except TelegramAPIError:
            log.warning("broadcast to %s failed", chat_id, exc_info=True)
            return "failed"
    return "failed"
