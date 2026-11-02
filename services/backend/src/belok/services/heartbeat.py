import asyncio
import logging

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from belok.db.models import Heartbeat
from belok.timeutil import utcnow

log = logging.getLogger(__name__)

BOT_INTERVAL = 60


async def beat(session: AsyncSession, name: str) -> None:
    stmt = insert(Heartbeat).values(name=name, beat_at=utcnow())
    await session.execute(
        stmt.on_conflict_do_update(index_elements=[Heartbeat.name], set_={"beat_at": utcnow()})
    )
    await session.commit()


async def run_heartbeat(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            async with sessionmaker() as session:
                await beat(session, "bot")
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("heartbeat failed")
        await asyncio.sleep(BOT_INTERVAL)
