from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import BodyWeight, DailyActivity, LlmUsage, Meal, MealItem, User, WorkoutSet
from belok.domain.nutrition import Macros
from belok.services.targets import Target, target_on


async def upsert_weight(session: AsyncSession, user_id: int, day: date, weight_kg: float) -> None:
    stmt = insert(BodyWeight).values(user_id=user_id, day=day, weight_kg=weight_kg)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "day"], set_={"weight_kg": stmt.excluded.weight_kg}
        )
    )


async def upsert_steps(session: AsyncSession, user_id: int, day: date, steps: int) -> None:
    stmt = insert(DailyActivity).values(user_id=user_id, day=day, steps=steps, water_ml=0)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "day"], set_={"steps": stmt.excluded.steps}
        )
    )


MAX_WATER_ML = 10_000
CLARIFY_KIND = "clarify"
CHAT_KIND = "chat"
REVIEW_KIND = "review"
# LLM calls that don't count toward the daily food analysis limit.
FREE_KINDS = (CLARIFY_KIND, CHAT_KIND, REVIEW_KIND)


async def add_water(session: AsyncSession, user_id: int, day: date, delta_ml: int) -> int:
    stmt = insert(DailyActivity).values(
        user_id=user_id, day=day, steps=0, water_ml=max(0, min(MAX_WATER_ML, delta_ml))
    )
    total = func.greatest(0, func.least(MAX_WATER_ML, DailyActivity.water_ml + delta_ml))
    return await session.scalar(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "day"], set_={"water_ml": total}
        ).returning(DailyActivity.water_ml)
    )


async def latest_weight(session: AsyncSession, user_id: int) -> float | None:
    return await session.scalar(
        select(BodyWeight.weight_kg)
        .where(BodyWeight.user_id == user_id)
        .order_by(BodyWeight.day.desc())
        .limit(1)
    )


async def recent_weights(session: AsyncSession, user_id: int, limit: int) -> list[BodyWeight]:
    result = await session.scalars(
        select(BodyWeight)
        .where(BodyWeight.user_id == user_id)
        .order_by(BodyWeight.day.desc())
        .limit(limit)
    )
    return list(result)


async def meals_on(session: AsyncSession, user_id: int, day: date) -> list[Meal]:
    result = await session.scalars(
        select(Meal).where(Meal.user_id == user_id, Meal.day == day).order_by(Meal.created_at)
    )
    return list(result)


async def get_meal(session: AsyncSession, user_id: int, meal_id: int) -> Meal | None:
    return await session.scalar(select(Meal).where(Meal.id == meal_id, Meal.user_id == user_id))


async def analyses_on(session: AsyncSession, user_id: int, day: date) -> int:
    return await session.scalar(
        select(func.count())
        .select_from(LlmUsage)
        .where(
            LlmUsage.user_id == user_id,
            LlmUsage.day == day,
            LlmUsage.ok.is_(True),
            LlmUsage.kind.not_in(FREE_KINDS),
        )
    )


@dataclass(frozen=True, slots=True)
class DaySummary:
    eaten: Macros
    target: Target | None
    meals: int
    steps: int
    water_ml: int
    sets: int
    weight_kg: float | None


async def day_summary(session: AsyncSession, user: User, day: date) -> DaySummary:
    meals = await meals_on(session, user.id, day)
    eaten = Macros()
    for meal in meals:
        eaten += meal.totals()

    activity = await session.scalar(
        select(DailyActivity).where(DailyActivity.user_id == user.id, DailyActivity.day == day)
    )
    sets = (
        await session.scalar(
            select(func.count())
            .select_from(WorkoutSet)
            .where(WorkoutSet.user_id == user.id, WorkoutSet.day == day)
        )
        or 0
    )
    weight = await latest_weight(session, user.id)

    target = None
    if user.profile_complete and weight is not None:
        target = await target_on(session, user, day, weight)
    return DaySummary(
        eaten,
        target,
        len(meals),
        activity.steps if activity else 0,
        activity.water_ml if activity else 0,
        sets,
        weight,
    )


@dataclass(frozen=True, slots=True)
class DayStats:
    day: date
    eaten: Macros
    steps: int
    water_ml: int
    sets: int


async def daily_stats(
    session: AsyncSession, user_id: int, start: date, end: date
) -> list[DayStats]:
    meal_rows = await session.execute(
        select(
            Meal.day,
            func.sum(MealItem.kcal * Meal.scale),
            func.sum(MealItem.protein * Meal.scale),
            func.sum(MealItem.fat * Meal.scale),
            func.sum(MealItem.carbs * Meal.scale),
        )
        .join(MealItem, MealItem.meal_id == Meal.id)
        .where(Meal.user_id == user_id, Meal.day.between(start, end))
        .group_by(Meal.day)
    )
    eaten = {day: Macros(*values) for day, *values in meal_rows}
    activity = {
        a.day: a
        for a in await session.scalars(
            select(DailyActivity).where(
                DailyActivity.user_id == user_id, DailyActivity.day.between(start, end)
            )
        )
    }
    sets = dict(
        (
            await session.execute(
                select(WorkoutSet.day, func.count())
                .where(WorkoutSet.user_id == user_id, WorkoutSet.day.between(start, end))
                .group_by(WorkoutSet.day)
            )
        ).all()
    )
    days = []
    day = start
    while day <= end:
        a = activity.get(day)
        days.append(
            DayStats(
                day,
                eaten.get(day, Macros()),
                a.steps if a else 0,
                a.water_ml if a else 0,
                sets.get(day, 0),
            )
        )
        day += timedelta(days=1)
    return days
