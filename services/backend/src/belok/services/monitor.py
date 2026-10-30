import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from belok.db.models import LlmUsage
from belok.services import stats
from belok.services.notify import notify_admins
from belok.timeutil import utcnow

log = logging.getLogger(__name__)

CHECK_INTERVAL = 300
ERROR_WINDOW = timedelta(hours=1)
ERROR_MIN_REQUESTS = 5
ERROR_RATE_THRESHOLD = 0.2
SUMMARY_HOUR = 21


async def run_monitor(
    bot: Bot, sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, tz: str
) -> None:
    while True:
        try:
            async with sessionmaker() as session:
                await check_errors(bot, session, redis)
                await daily_summary(bot, session, redis, tz)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("monitor check failed")
        await asyncio.sleep(CHECK_INTERVAL)


async def check_errors(bot: Bot, session: AsyncSession, redis: Redis) -> None:
    total, errors = (
        await session.execute(
            select(func.count(), func.count().filter(LlmUsage.ok.is_(False))).where(
                LlmUsage.created_at >= utcnow() - ERROR_WINDOW
            )
        )
    ).one()
    if total < ERROR_MIN_REQUESTS or errors / total <= ERROR_RATE_THRESHOLD:
        return
    if not await redis.set(
        "belok:alert:llm_errors", 1, nx=True, ex=int(ERROR_WINDOW.total_seconds())
    ):
        return
    await notify_admins(
        bot,
        session,
        "errors",
        f"⚠️ Ошибки распознавания: {errors} из {total} за последний час "
        f"({errors / total:.0%}). Проверь ключ и баланс Anthropic.",
    )


async def daily_summary(bot: Bot, session: AsyncSession, redis: Redis, tz: str) -> None:
    now = utcnow()
    local = now.astimezone(ZoneInfo(tz))
    if local.hour < SUMMARY_HOUR:
        return
    if not await redis.set(f"belok:summary:{local.date()}", 1, nx=True, ex=2 * 86400):
        return
    await notify_admins(bot, session, "daily", await summary_text(session, now, tz))


async def summary_text(session: AsyncSession, now: datetime, tz: str) -> str:
    d = await stats.dashboard(session, now, tz, days=1)
    errors = f"{d.error_rate_24h:.0%}" if d.error_rate_24h is not None else "нет запросов"
    return (
        "<b>Белок за сегодня</b>\n"
        f"Новых: {d.new_today} · всего {d.users_total}\n"
        f"Активных: {d.dau} · за неделю {d.wau} · за месяц {d.mau}\n"
        f"Триал {d.statuses['trial']} · подписка {d.statuses['active'] + d.statuses['lifetime']}"
        f" · истёк {d.statuses['expired']}\n"
        f"LLM: ${d.cost_today:.2f} сегодня · ${d.cost_month:.2f} за месяц"
        f" · прогноз ${d.cost_forecast:.2f}\n"
        f"Распознаваний за сутки: {d.requests_24h} · ошибок {errors}"
    )
