from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import BodyWeight, DailyActivity, LlmUsage, Meal, User, WorkoutSet
from belok.domain.nutrition import Macros, daily_target


async def upsert_weight(session: AsyncSession, user_id: int, day: date, weight_kg: float) -> None:
    stmt = insert(BodyWeight).values(user_id=user_id, day=day, weight_kg=weight_kg)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "day"], set_={"weight_kg": stmt.excluded.weight_kg}
        )
    )


async def upsert_steps(session: AsyncSession, user_id: int, day: date, steps: int) -> None:
    stmt = insert(DailyActivity).values(user_id=user_id, day=day, steps=steps)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "day"], set_={"steps": stmt.excluded.steps}
        )
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
        .where(LlmUsage.user_id == user_id, LlmUsage.day == day, LlmUsage.ok.is_(True))
    )


@dataclass(frozen=True, slots=True)
class DaySummary:
    eaten: Macros
    target: Macros | None
    meals: int
    steps: int
    sets: int
    weight_kg: float | None


async def day_summary(session: AsyncSession, user: User, day: date) -> DaySummary:
    meals = await meals_on(session, user.id, day)
    eaten = Macros()
    for meal in meals:
        eaten += meal.totals()

    steps = (
        await session.scalar(
            select(DailyActivity.steps).where(
                DailyActivity.user_id == user.id, DailyActivity.day == day
            )
        )
        or 0
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
        target = daily_target(
            user.sex, weight, user.height_cm, day.year - user.birth_year, user.goal, steps, sets
        )
    return DaySummary(eaten, target, len(meals), steps, sets, weight)
