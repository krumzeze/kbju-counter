from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import (
    AdminAction,
    DailyActivity,
    LlmUsage,
    Meal,
    PromoCode,
    PromoRedemption,
    User,
    WorkoutSet,
)
from belok.services.stats import status_case

INACTIVE_AFTER = timedelta(days=7)


class UserFilter(StrEnum):
    ALL = "all"
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    BLOCKED = "blocked"
    INACTIVE = "inactive"
    ADMINS = "admins"


class Segment(StrEnum):
    ALL = "all"
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    INACTIVE = "inactive"


class UserSort(StrEnum):
    CREATED = "created_at"
    SEEN = "last_seen_at"
    ANALYSES = "analyses"
    COST = "cost"
    ACCESS = "access_until"


@dataclass(slots=True)
class UserRow:
    user: User
    status: str
    analyses: int
    cost_usd: float


def _status_filter(name: str, now: datetime):
    match name:
        case "trial" | "active" | "expired":
            if name == "active":
                return status_case(now).in_(("active", "lifetime"))
            return status_case(now) == name
        case "blocked":
            return User.is_blocked.is_(True)
        case "inactive":
            return or_(User.last_seen_at.is_(None), User.last_seen_at < now - INACTIVE_AFTER)
        case "admins":
            return User.is_admin.is_(True)
    return None


def segment_filter(segment: Segment, now: datetime) -> list:
    where = [User.is_blocked.is_(False), User.bot_blocked.is_(False)]
    condition = _status_filter(segment.value, now)
    if condition is not None:
        where.append(condition)
    return where


def search_filter(query: str):
    query = query.strip().lstrip("@")
    if query.isdigit():
        return User.id == int(query)
    pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    return or_(User.username.ilike(pattern), User.first_name.ilike(pattern))


async def list_users(
    session: AsyncSession,
    now: datetime,
    query: str | None,
    user_filter: UserFilter,
    sort: UserSort,
    descending: bool,
    offset: int,
    limit: int,
) -> tuple[list[UserRow], int]:
    usage = (
        select(
            LlmUsage.user_id,
            func.count().filter(LlmUsage.ok.is_(True)).label("analyses"),
            func.coalesce(func.sum(LlmUsage.cost_usd), 0.0).label("cost"),
        )
        .group_by(LlmUsage.user_id)
        .subquery()
    )
    analyses = func.coalesce(usage.c.analyses, 0)
    cost = func.coalesce(usage.c.cost, 0.0)
    access = func.greatest(
        User.trial_ends_at, func.coalesce(User.subscription_until, User.trial_ends_at)
    )
    columns = {
        UserSort.CREATED: User.created_at,
        UserSort.SEEN: User.last_seen_at,
        UserSort.ANALYSES: analyses,
        UserSort.COST: cost,
        UserSort.ACCESS: access,
    }

    where = []
    if query and query.strip():
        where.append(search_filter(query))
    condition = _status_filter(user_filter.value, now)
    if condition is not None:
        where.append(condition)

    order = columns[sort].desc().nulls_last() if descending else columns[sort].asc().nulls_first()
    rows = await session.execute(
        select(User, status_case(now), analyses, cost)
        .outerjoin(usage, usage.c.user_id == User.id)
        .where(*where)
        .order_by(order, User.id)
        .offset(offset)
        .limit(limit)
    )
    total = await session.scalar(select(func.count()).select_from(User).where(*where))
    return [UserRow(u, s, a, float(c)) for u, s, a, c in rows.all()], total


@dataclass(slots=True)
class ActivityDay:
    day: date
    meals: int = 0
    sets: int = 0
    steps: int = 0
    analyses: int = 0


async def activity(
    session: AsyncSession, user_id: int, since: date, until: date
) -> list[ActivityDay]:
    days = {
        since + timedelta(days=i): ActivityDay(since + timedelta(days=i))
        for i in range((until - since).days + 1)
    }
    in_range = (since, until)
    for day, n in await session.execute(
        select(Meal.day, func.count())
        .where(Meal.user_id == user_id, Meal.day.between(*in_range))
        .group_by(Meal.day)
    ):
        days[day].meals = n
    for day, n in await session.execute(
        select(WorkoutSet.day, func.count())
        .where(WorkoutSet.user_id == user_id, WorkoutSet.day.between(*in_range))
        .group_by(WorkoutSet.day)
    ):
        days[day].sets = n
    for day, n in await session.execute(
        select(DailyActivity.day, DailyActivity.steps).where(
            DailyActivity.user_id == user_id, DailyActivity.day.between(*in_range)
        )
    ):
        days[day].steps = n
    for day, n in await session.execute(
        select(LlmUsage.day, func.count())
        .where(LlmUsage.user_id == user_id, LlmUsage.day.between(*in_range))
        .group_by(LlmUsage.day)
    ):
        days[day].analyses = n
    return list(days.values())


async def recent_meals(session: AsyncSession, user_id: int, limit: int) -> list[Meal]:
    result = await session.scalars(
        select(Meal).where(Meal.user_id == user_id).order_by(Meal.created_at.desc()).limit(limit)
    )
    return list(result)


async def recent_llm(session: AsyncSession, user_id: int, limit: int) -> list[LlmUsage]:
    result = await session.scalars(
        select(LlmUsage)
        .where(LlmUsage.user_id == user_id)
        .order_by(LlmUsage.created_at.desc())
        .limit(limit)
    )
    return list(result)


async def llm_totals(session: AsyncSession, user_id: int) -> tuple[int, int, float]:
    total, errors, cost = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(LlmUsage.ok.is_(False)),
                func.coalesce(func.sum(LlmUsage.cost_usd), 0.0),
            ).where(LlmUsage.user_id == user_id)
        )
    ).one()
    return total, errors, float(cost)


async def redemptions(session: AsyncSession, user_id: int) -> list[tuple[str, int, datetime]]:
    rows = await session.execute(
        select(PromoCode.code, PromoCode.days, PromoRedemption.created_at)
        .join(PromoCode)
        .where(PromoRedemption.user_id == user_id)
        .order_by(PromoRedemption.created_at.desc())
    )
    return [tuple(r) for r in rows.all()]


async def actions_on(session: AsyncSession, user_id: int, limit: int) -> list[AdminAction]:
    result = await session.scalars(
        select(AdminAction)
        .where(AdminAction.target_user_id == user_id)
        .order_by(AdminAction.created_at.desc())
        .limit(limit)
    )
    return list(result)
