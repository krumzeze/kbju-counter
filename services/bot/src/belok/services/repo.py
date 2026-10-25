from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import (
    BodyWeight,
    DailyActivity,
    Exercise,
    LlmUsage,
    Meal,
    User,
    WorkoutSet,
)
from belok.domain.nutrition import Macros, daily_target
from belok.domain.workouts import ParsedSet


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


async def get_or_create_exercise(session: AsyncSession, user_id: int, name: str) -> Exercise:
    stmt = (
        insert(Exercise)
        .values(user_id=user_id, name=name)
        .on_conflict_do_nothing(index_elements=["user_id", "name"])
    )
    await session.execute(stmt)
    return await session.scalar(
        select(Exercise).where(Exercise.user_id == user_id, Exercise.name == name)
    )


async def add_sets(
    session: AsyncSession, user_id: int, exercise: Exercise, day: date, sets: list[ParsedSet]
) -> None:
    session.add_all(
        WorkoutSet(
            user_id=user_id, exercise_id=exercise.id, day=day, weight_kg=s.weight_kg, reps=s.reps
        )
        for s in sets
    )


async def list_exercises(session: AsyncSession, user_id: int) -> list[str]:
    result = await session.scalars(
        select(Exercise.name).where(Exercise.user_id == user_id).order_by(Exercise.name)
    )
    return list(result)


async def exercise_history(
    session: AsyncSession, user_id: int, name: str, limit: int
) -> list[tuple[date, list[WorkoutSet]]]:
    days = (
        await session.scalars(
            select(WorkoutSet.day)
            .join(Exercise)
            .where(Exercise.user_id == user_id, Exercise.name == name)
            .group_by(WorkoutSet.day)
            .order_by(WorkoutSet.day.desc())
            .limit(limit)
        )
    ).all()
    if not days:
        return []
    sets = await session.scalars(
        select(WorkoutSet)
        .join(Exercise)
        .where(Exercise.user_id == user_id, Exercise.name == name, WorkoutSet.day.in_(days))
        .order_by(WorkoutSet.day, WorkoutSet.id)
    )
    by_day: dict[date, list[WorkoutSet]] = {}
    for s in sets:
        by_day.setdefault(s.day, []).append(s)
    return sorted(by_day.items())


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
    meals = list(
        await session.scalars(select(Meal).where(Meal.user_id == user.id, Meal.day == day))
    )
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
