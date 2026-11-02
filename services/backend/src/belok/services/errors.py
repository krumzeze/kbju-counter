import hashlib
import logging
import re
import traceback
from datetime import timedelta
from html import escape

from aiogram import Bot
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from belok.db.models import AppError
from belok.services.notify import notify_admins
from belok.timeutil import utcnow

log = logging.getLogger(__name__)

REALERT_AFTER = timedelta(hours=1)
MAX_ALERTS_PER_HOUR = 10
MAX_NEW_WEB_PER_HOUR = 50
RETENTION = timedelta(days=30)
MAX_MESSAGE = 500
MAX_DETAIL = 8000

SOURCES = {"api": "API", "bot": "бот", "web": "приложение"}


def _hash(*parts: str) -> str:
    return hashlib.sha1("\x00".join(parts).encode(), usedforsecurity=False).hexdigest()


def _origin(exc: BaseException) -> str:
    """Innermost frame of our own code, without the line number so edits don't split groups."""
    frames = traceback.extract_tb(exc.__traceback__)
    ours = [f for f in frames if "/belok/" in f.filename and "site-packages" not in f.filename]
    frame = (ours or frames or [None])[-1]
    if frame is None:
        return ""
    return f"{frame.filename.rsplit('/belok/', 1)[-1]}:{frame.name}"


def describe(exc: BaseException) -> tuple[str, str, str]:
    """Returns fingerprint, one-line message and the formatted traceback."""
    name = type(exc).__name__
    origin = _origin(exc)
    message = f"{name}: {exc}" if str(exc) else name
    if origin:
        message = f"{message} ({origin})"
    detail = "".join(traceback.format_exception(exc))
    return _hash(name, origin), message, detail


def web_fingerprint(message: str) -> str:
    return _hash("web", re.sub(r"\d+", "N", message))


async def record(
    session: AsyncSession,
    bot: Bot,
    *,
    source: str,
    fingerprint: str,
    message: str,
    detail: str | None = None,
    path: str | None = None,
    user_id: int | None = None,
) -> None:
    now = utcnow()
    hour_ago = now - timedelta(hours=1)
    if source == "web" and await session.get(AppError, fingerprint) is None:
        fresh = await session.scalar(
            select(func.count())
            .select_from(AppError)
            .where(AppError.source == "web", AppError.first_seen >= hour_ago)
        )
        if fresh >= MAX_NEW_WEB_PER_HOUR:
            return

    values = {
        "message": message[:MAX_MESSAGE],
        "detail": detail[:MAX_DETAIL] if detail else None,
        "path": path[:256] if path else None,
        "user_id": user_id,
        "last_seen": now,
    }
    stmt = insert(AppError).values(
        fingerprint=fingerprint, source=source, count=1, first_seen=now, **values
    )
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[AppError.fingerprint],
            set_={**values, "count": AppError.count + 1},
        )
    )
    await session.commit()

    alerts = await session.scalar(
        select(func.count()).select_from(AppError).where(AppError.alerted_at >= hour_ago)
    )
    if alerts >= MAX_ALERTS_PER_HOUR:
        return
    row = await session.scalar(
        update(AppError)
        .where(
            AppError.fingerprint == fingerprint,
            or_(AppError.alerted_at.is_(None), AppError.alerted_at < now - REALERT_AFTER),
        )
        .values(alerted_at=now)
        .returning(AppError)
    )
    await session.commit()
    if row is not None:
        await notify_admins(bot, session, "errors", alert_text(row))


def alert_text(row: AppError) -> str:
    head = "🔥 Новая ошибка" if row.count == 1 else f"🔁 Ошибка повторяется ({row.count} раз)"
    lines = [f"{head}: {SOURCES.get(row.source, row.source)}"]
    if row.path:
        lines.append(f"<code>{escape(row.path)}</code>")
    lines.append(escape(row.message))
    if row.user_id:
        lines.append(f"Пользователь <code>{row.user_id}</code>")
    lines.append("<i>Подробности в админке, раздел «Система».</i>")
    return "\n".join(lines)


async def capture(
    sessionmaker: async_sessionmaker[AsyncSession],
    bot: Bot,
    exc: BaseException,
    source: str,
    path: str | None = None,
    user_id: int | None = None,
) -> None:
    """Records an unhandled exception in a fresh session; never raises."""
    try:
        fingerprint, message, detail = describe(exc)
        async with sessionmaker() as session:
            await record(
                session,
                bot,
                source=source,
                fingerprint=fingerprint,
                message=message,
                detail=detail,
                path=path,
                user_id=user_id,
            )
    except Exception:
        log.exception("failed to record error")


async def recent(session: AsyncSession, limit: int = 50) -> list[AppError]:
    rows = await session.scalars(select(AppError).order_by(AppError.last_seen.desc()).limit(limit))
    return list(rows.all())


async def resolve(session: AsyncSession, fingerprint: str | None = None) -> None:
    stmt = delete(AppError)
    if fingerprint is not None:
        stmt = stmt.where(AppError.fingerprint == fingerprint)
    await session.execute(stmt)
    await session.commit()


async def prune(session: AsyncSession) -> None:
    await session.execute(delete(AppError).where(AppError.last_seen < utcnow() - RETENTION))
    await session.commit()
