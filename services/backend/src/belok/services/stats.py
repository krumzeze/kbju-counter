import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Date, and_, case, cast, func, literal, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import (
    BodyWeight,
    DailyActivity,
    LlmUsage,
    Meal,
    PromoRedemption,
    ReferralReward,
    User,
    WorkoutSet,
)


@dataclass(slots=True)
class DayPoint:
    day: date
    new_users: int = 0
    active_users: int = 0
    analyses: int = 0
    errors: int = 0
    cost_usd: float = 0.0


@dataclass(slots=True)
class Dashboard:
    users_total: int
    new_today: int
    new_7d: int
    new_30d: int
    dau: int
    wau: int
    mau: int
    statuses: dict[str, int]
    blocked: int
    bot_blocked: int
    funnel: list[tuple[str, int]]
    cost_today: float
    cost_month: float
    cost_forecast: float
    avg_cost: float | None
    requests_24h: int
    error_rate_24h: float | None
    no_food_rate_24h: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    referred_users: int
    referral_rewards: int
    promo_redemptions_30d: int
    sources: list[tuple[str, int]]
    series: list[DayPoint] = field(default_factory=list)


def activity_days():
    """(user_id, day) pairs for every day a user logged anything."""
    return union(
        select(Meal.user_id, Meal.day),
        select(WorkoutSet.user_id, WorkoutSet.day),
        select(DailyActivity.user_id, DailyActivity.day),
        select(BodyWeight.user_id, BodyWeight.day),
    ).subquery()


def status_case(now: datetime):
    return case(
        (User.lifetime_access.is_(True), literal("lifetime")),
        (User.subscription_until > now, literal("active")),
        (User.trial_ends_at > now, literal("trial")),
        else_=literal("expired"),
    )


async def dashboard(session: AsyncSession, now: datetime, tz: str, days: int = 30) -> Dashboard:
    zone = ZoneInfo(tz)
    today = now.astimezone(zone).date()
    day_start = datetime.combine(today, time(), zone)
    month_start = datetime.combine(today.replace(day=1), time(), zone)
    since = today - timedelta(days=days - 1)

    def count_users(*where):
        return select(func.count()).select_from(User).where(*where).scalar_subquery()

    users = (
        await session.execute(
            select(
                count_users(),
                count_users(User.created_at >= day_start),
                count_users(User.created_at >= day_start - timedelta(days=6)),
                count_users(User.created_at >= day_start - timedelta(days=29)),
                count_users(User.is_blocked.is_(True)),
                count_users(User.bot_blocked.is_(True)),
                count_users(User.referred_by_id.is_not(None)),
            )
        )
    ).one()

    statuses = dict.fromkeys(("trial", "active", "lifetime", "expired"), 0)
    by_status = select(status_case(now).label("status")).subquery()
    rows = await session.execute(
        select(by_status.c.status, func.count()).group_by(by_status.c.status)
    )
    statuses.update({status: n for status, n in rows.all()})

    act = activity_days()

    def active_since(start: date):
        return (
            select(func.count(func.distinct(act.c.user_id)))
            .where(act.c.day >= start)
            .scalar_subquery()
        )

    dau, wau, mau = (
        await session.execute(
            select(
                active_since(today),
                active_since(today - timedelta(days=6)),
                active_since(today - timedelta(days=29)),
            )
        )
    ).one()

    profile_done = and_(
        User.sex.is_not(None),
        User.birth_year.is_not(None),
        User.height_cm.is_not(None),
        User.goal.is_not(None),
    )
    loyal = (
        select(act.c.user_id).group_by(act.c.user_id).having(func.count(act.c.day) >= 3).subquery()
    )
    funnel_counts = (
        await session.execute(
            select(
                count_users(),
                count_users(profile_done),
                select(func.count(func.distinct(Meal.user_id))).scalar_subquery(),
                select(func.count()).select_from(loyal).scalar_subquery(),
            )
        )
    ).one()
    funnel = list(
        zip(
            ("registered", "profile", "first_meal", "active_3_days"),
            funnel_counts,
            strict=True,
        )
    )

    cost = func.coalesce(func.sum(LlmUsage.cost_usd), 0.0)
    cost_today, cost_month = (
        await session.execute(
            select(
                select(cost).where(LlmUsage.created_at >= day_start).scalar_subquery(),
                select(cost).where(LlmUsage.created_at >= month_start).scalar_subquery(),
            )
        )
    ).one()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    elapsed = (now - month_start).total_seconds() / 86400
    forecast = cost_month / elapsed * days_in_month if elapsed > 0 else 0.0

    avg_cost = await session.scalar(
        select(func.avg(LlmUsage.cost_usd)).where(
            LlmUsage.ok.is_(True), LlmUsage.created_at >= now - timedelta(days=30)
        )
    )

    last_day = LlmUsage.created_at >= now - timedelta(hours=24)
    total_24h, errors_24h, no_food_24h, p50, p95 = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(LlmUsage.ok.is_(False)),
                func.count().filter(LlmUsage.no_food.is_(True)),
                func.percentile_cont(0.5)
                .within_group(LlmUsage.latency_ms)
                .filter(LlmUsage.ok.is_(True)),
                func.percentile_cont(0.95)
                .within_group(LlmUsage.latency_ms)
                .filter(LlmUsage.ok.is_(True)),
            ).where(last_day)
        )
    ).one()

    rewards = await session.scalar(select(func.count()).select_from(ReferralReward))
    redemptions = await session.scalar(
        select(func.count())
        .select_from(PromoRedemption)
        .where(PromoRedemption.created_at >= day_start - timedelta(days=29))
    )
    source = case(
        (User.referred_by_id.is_not(None), literal("referral")),
        else_=func.coalesce(User.source, literal("direct")),
    )
    recent = (
        select(source.label("source"))
        .where(User.created_at >= day_start - timedelta(days=29))
        .subquery()
    )
    source_rows = await session.execute(
        select(recent.c.source, func.count())
        .group_by(recent.c.source)
        .order_by(func.count().desc())
        .limit(10)
    )

    return Dashboard(
        users_total=users[0],
        new_today=users[1],
        new_7d=users[2],
        new_30d=users[3],
        dau=dau,
        wau=wau,
        mau=mau,
        statuses=statuses,
        blocked=users[4],
        bot_blocked=users[5],
        funnel=funnel,
        cost_today=float(cost_today),
        cost_month=float(cost_month),
        cost_forecast=float(forecast),
        avg_cost=float(avg_cost) if avg_cost is not None else None,
        requests_24h=total_24h,
        error_rate_24h=errors_24h / total_24h if total_24h else None,
        no_food_rate_24h=no_food_24h / total_24h if total_24h else None,
        latency_p50_ms=p50,
        latency_p95_ms=p95,
        referred_users=users[6],
        referral_rewards=rewards,
        promo_redemptions_30d=redemptions,
        sources=[(s, n) for s, n in source_rows.all()],
        series=await _series(session, since, today, tz, act),
    )


async def _series(session: AsyncSession, since: date, today: date, tz: str, act) -> list[DayPoint]:
    points = {
        since + timedelta(days=i): DayPoint(since + timedelta(days=i))
        for i in range((today - since).days + 1)
    }

    created_day = cast(func.timezone(tz, User.created_at), Date)
    for day, n in await session.execute(
        select(created_day, func.count()).where(created_day >= since).group_by(created_day)
    ):
        points[day].new_users = n

    for day, n in await session.execute(
        select(act.c.day, func.count(func.distinct(act.c.user_id)))
        .where(act.c.day >= since, act.c.day <= today)
        .group_by(act.c.day)
    ):
        points[day].active_users = n

    for day, total, errors, cost in await session.execute(
        select(
            LlmUsage.day,
            func.count(),
            func.count().filter(LlmUsage.ok.is_(False)),
            func.coalesce(func.sum(LlmUsage.cost_usd), 0.0),
        )
        .where(LlmUsage.day >= since, LlmUsage.day <= today)
        .group_by(LlmUsage.day)
    ):
        points[day].analyses = total
        points[day].errors = errors
        points[day].cost_usd = float(cost)

    return list(points.values())
