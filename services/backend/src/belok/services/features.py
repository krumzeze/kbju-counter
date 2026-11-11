import time
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import FeatureFlag

CACHE_SECONDS = 15


class Feature(StrEnum):
    PHOTO = "photo"
    TEXT = "text"
    VOICE = "voice"
    BARCODE = "barcode"
    REMINDERS = "reminders"
    PAYMENTS = "payments"
    WIDGETS = "widgets"


class FeatureDisabled(Exception):
    pass


_cache: dict[str, bool] = {}
_loaded_at: float | None = None


async def flags(session: AsyncSession) -> dict[Feature, bool]:
    global _cache, _loaded_at
    if _loaded_at is None or time.monotonic() - _loaded_at > CACHE_SECONDS:
        rows = await session.execute(select(FeatureFlag.key, FeatureFlag.enabled))
        _cache = dict(rows.all())
        _loaded_at = time.monotonic()
    return {f: _cache.get(f.value, True) for f in Feature}


async def enabled(session: AsyncSession, feature: Feature) -> bool:
    return (await flags(session))[feature]


async def ensure_enabled(session: AsyncSession, feature: Feature) -> None:
    if not await enabled(session, feature):
        raise FeatureDisabled(feature)


async def set_enabled(session: AsyncSession, feature: Feature, value: bool) -> None:
    """Commits, so the local cache never reloads the old value in between."""
    stmt = insert(FeatureFlag).values(key=feature.value, enabled=value)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[FeatureFlag.key], set_={"enabled": value, "updated_at": func.now()}
        )
    )
    await session.commit()
    reset_cache()


def reset_cache() -> None:
    global _loaded_at
    _loaded_at = None
