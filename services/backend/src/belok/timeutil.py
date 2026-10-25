from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    return datetime.now(UTC)


def local_today(tz: str) -> date:
    return datetime.now(ZoneInfo(tz)).date()
