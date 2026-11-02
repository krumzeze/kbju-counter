from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import BodyWeight, Meal, MealItem, User
from belok.domain import adaptive
from belok.domain.nutrition import Macros, bmr, maintenance_kcal, target_for
from belok.services.workouts import activity_kcal


class TargetSource(StrEnum):
    FORMULA = "formula"
    ADAPTIVE = "adaptive"


@dataclass(frozen=True, slots=True)
class Target:
    macros: Macros
    source: TargetSource
    # Activity kcal added on top of the formula; zero when the target is adaptive.
    activity_kcal: float
    estimate: adaptive.Estimate


async def daily_intake(
    session: AsyncSession, user_id: int, start: date, end: date
) -> dict[date, float]:
    rows = await session.execute(
        select(Meal.day, func.sum(MealItem.kcal * Meal.scale))
        .join(MealItem, MealItem.meal_id == Meal.id)
        .where(Meal.user_id == user_id, Meal.day.between(start, end))
        .group_by(Meal.day)
    )
    return {day: kcal for day, kcal in rows.all()}


async def weights_between(
    session: AsyncSession, user_id: int, start: date, end: date
) -> list[tuple[date, float]]:
    rows = await session.execute(
        select(BodyWeight.day, BodyWeight.weight_kg).where(
            BodyWeight.user_id == user_id, BodyWeight.day.between(start, end)
        )
    )
    return [(d, w) for d, w in rows.all()]


async def adaptive_estimate(
    session: AsyncSession, user_id: int, day: date, formula_kcal: float
) -> adaptive.Estimate:
    start, end = adaptive.window(day)
    intake = await daily_intake(session, user_id, start, end)
    weights = await weights_between(session, user_id, start, end)
    return adaptive.estimate(intake, weights, formula_kcal)


async def target_on(session: AsyncSession, user: User, day: date, weight_kg: float) -> Target:
    age = day.year - user.birth_year
    activity = await activity_kcal(session, user.id, day, weight_kg)
    formula = maintenance_kcal(user.sex, weight_kg, user.height_cm, age, activity)
    estimate = await adaptive_estimate(session, user.id, day, formula)

    if user.adaptive_target and estimate.tdee is not None:
        # The measured expenditure already contains the user's usual activity.
        tdee = estimate.tdee if user.activity_adjust else estimate.tdee - activity
        source, shown_activity = TargetSource.ADAPTIVE, 0.0
    else:
        shown_activity = activity if user.activity_adjust else 0.0
        tdee = formula - activity + shown_activity
        source = TargetSource.FORMULA

    floor = bmr(user.sex, weight_kg, user.height_cm, age)
    macros = target_for(tdee, weight_kg, user.goal, floor_kcal=floor)
    return Target(macros, source, shown_activity, estimate)
