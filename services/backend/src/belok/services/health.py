import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from aiogram import Bot
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import Heartbeat, LlmUsage
from belok.llm.analyzer import FoodAnalyzer
from belok.llm.speech import SpeechToText
from belok.services import heartbeat, monitor, reminders, reviews
from belok.services.products import FoodDatabase
from belok.services.tribute import TributeCatalog
from belok.timeutil import utcnow

log = logging.getLogger(__name__)

TIMEOUT = 12
# A worker is considered dead after missing this many beats.
MISSED_BEATS = 3
WORKERS = {
    "bot": heartbeat.BOT_INTERVAL,
    "reminders": reminders.CHECK_INTERVAL,
    "reviews": reviews.CHECK_INTERVAL,
    "monitor": monitor.CHECK_INTERVAL,
}
LLM_WINDOW = timedelta(hours=1)


class Status(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    OFF = "off"


@dataclass(frozen=True, slots=True)
class Check:
    key: str
    status: Status
    detail: str | None = None
    latency_ms: int | None = None


@dataclass(frozen=True, slots=True)
class Probes:
    redis_url: str
    bot: Bot
    analyzer: FoodAnalyzer
    stt: SpeechToText | None
    food_db: FoodDatabase
    tribute: TributeCatalog


async def run_checks(session: AsyncSession, probes: Probes) -> list[Check]:
    # The session can't be shared across tasks, so database checks run first.
    local = [await _timed("database", lambda: _database(session))]
    local += await _workers(session)
    remote = await asyncio.gather(
        _timed("redis", lambda: _redis(probes.redis_url)),
        _timed("telegram", lambda: _telegram(probes.bot)),
        _timed("anthropic", lambda: _anthropic(probes.analyzer)),
        _timed("stt", lambda: _stt(probes.stt)),
        _timed("food_db", lambda: _food_db(probes.food_db)),
        _timed("tribute", lambda: _tribute(probes.tribute)),
    )
    checks = local + list(remote)
    llm = await _llm_errors(session)
    return [_merge_llm(c, llm) if c.key == "anthropic" else c for c in checks]


async def _timed(key: str, probe: Callable[[], Awaitable[tuple[Status, str | None]]]) -> Check:
    started = time.monotonic()
    try:
        status, detail = await asyncio.wait_for(probe(), TIMEOUT)
    except TimeoutError:
        status, detail = Status.FAIL, f"нет ответа за {TIMEOUT} с"
    except Exception as exc:
        log.warning("health check %s failed", key, exc_info=True)
        status, detail = Status.FAIL, f"{type(exc).__name__}: {exc}"[:300]
    latency = None if status == Status.OFF else int((time.monotonic() - started) * 1000)
    return Check(key, status, detail, latency)


async def _database(session: AsyncSession) -> tuple[Status, str | None]:
    await session.execute(text("SELECT 1"))
    return Status.OK, None


async def _workers(session: AsyncSession) -> list[Check]:
    beats = dict((await session.execute(select(Heartbeat.name, Heartbeat.beat_at))).all())
    now = utcnow()
    checks = []
    for name, interval in WORKERS.items():
        at = beats.get(name)
        if at is None:
            checks.append(Check(f"worker:{name}", Status.FAIL, "ещё не выходил на связь"))
            continue
        age = int((now - at).total_seconds())
        status = Status.OK if age <= interval * MISSED_BEATS else Status.FAIL
        checks.append(Check(f"worker:{name}", status, f"последний сигнал {age} с назад"))
    return checks


async def _redis(url: str) -> tuple[Status, str | None]:
    redis = Redis.from_url(url)
    try:
        await redis.ping()
    finally:
        await redis.aclose()
    return Status.OK, None


async def _telegram(bot: Bot) -> tuple[Status, str | None]:
    me = await bot.get_me()
    return Status.OK, f"@{me.username}"


async def _anthropic(analyzer: FoodAnalyzer) -> tuple[Status, str | None]:
    await analyzer.ping()
    return Status.OK, analyzer.model


async def _stt(stt: SpeechToText | None) -> tuple[Status, str | None]:
    if stt is None:
        return Status.OFF, "не задан STT_API_KEY"
    await stt.ping()
    return Status.OK, stt.model


async def _food_db(food_db: FoodDatabase) -> tuple[Status, str | None]:
    await food_db.ping()
    return Status.OK, None


async def _tribute(tribute: TributeCatalog) -> tuple[Status, str | None]:
    if not tribute.enabled:
        return Status.OFF, "не задан TRIBUTE_API_KEY"
    found = await tribute.ping()
    total = tribute.plan_count
    if found < total:
        return Status.WARN, f"в Tribute найдено {found} из {total} тарифов"
    return Status.OK, f"тарифов: {found}"


async def _llm_errors(session: AsyncSession) -> tuple[int, int]:
    total, errors = (
        await session.execute(
            select(func.count(), func.count().filter(LlmUsage.ok.is_(False))).where(
                LlmUsage.created_at >= utcnow() - LLM_WINDOW
            )
        )
    ).one()
    return total, errors


def _merge_llm(check: Check, llm: tuple[int, int]) -> Check:
    total, errors = llm
    if check.status != Status.OK or total < monitor.ERROR_MIN_REQUESTS:
        return check
    if errors / total <= monitor.ERROR_RATE_THRESHOLD:
        return check
    return Check(
        check.key,
        Status.WARN,
        f"за час {errors} из {total} распознаваний с ошибкой",
        check.latency_ms,
    )
