"""A compact text snapshot of a user's data for the AI assistant.

All arithmetic happens here, so the model only reads ready numbers.
"""

from collections import Counter
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import Meal, User, Workout
from belok.domain.nutrition import Goal, Macros, Sex
from belok.services.recipes import per_portion, suggestions
from belok.services.repo import DayStats, daily_stats, day_summary, meals_on
from belok.services.targets import weights_between
from belok.services.workouts import summarize

GOALS = {Goal.LOSE: "lose weight", Goal.MAINTAIN: "maintain weight", Goal.GAIN: "gain weight"}
RECENT_DAYS = 7
LONG_DAYS = 28
WORKOUT_DAYS = 14
FREQUENT_FOODS = 10
APP_RECIPES = 4


def _m(m: Macros) -> str:
    return f"{m.kcal:.0f} kcal, P {m.protein:.0f} g, F {m.fat:.0f} g, C {m.carbs:.0f} g"


def _avg(days: list[DayStats]) -> Macros | None:
    logged = [d.eaten for d in days if d.eaten.kcal > 0]
    if not logged:
        return None
    n = len(logged)
    return Macros(
        sum(m.kcal for m in logged) / n,
        sum(m.protein for m in logged) / n,
        sum(m.fat for m in logged) / n,
        sum(m.carbs for m in logged) / n,
    )


async def snapshot(session: AsyncSession, user: User, today: date) -> str:
    lines = [f"Today: {today.isoformat()} ({today:%A}), the user's local date."]
    summary = await day_summary(session, user, today)
    target = summary.target.macros if summary.target else None

    profile = []
    if user.sex:
        profile.append("male" if user.sex == Sex.MALE else "female")
    if user.birth_year:
        profile.append(f"{today.year - user.birth_year} y")
    if user.height_cm:
        profile.append(f"{user.height_cm} cm")
    if summary.weight_kg:
        profile.append(f"weight {summary.weight_kg:.1f} kg")
    if user.goal:
        profile.append(f"goal: {GOALS[user.goal]}")
    lines.append("Profile: " + (", ".join(profile) or "not filled in") + ".")
    if target:
        source = summary.target.source.value
        lines.append(f"Daily target ({source}): {_m(target)}.")
    else:
        lines.append("Daily target: unknown (profile or weight missing).")

    lines.append(f"Today so far: {_m(summary.eaten)}.")
    if target:
        left = Macros(
            target.kcal - summary.eaten.kcal,
            target.protein - summary.eaten.protein,
            target.fat - summary.eaten.fat,
            target.carbs - summary.eaten.carbs,
        )
        lines.append(f"Left for today (negative means over): {_m(left)}.")
        fitting = await suggestions(session, user, left)
        if fitting:
            lines.append("Recipes in the app that best fill what's left today (per portion):")
            for recipe, cover in fitting[:APP_RECIPES]:
                covered = ", ".join(f"{k} {v}%" for k, v in cover.items())
                lines.append(f"- {recipe.title}: {_m(per_portion(recipe))}; covers {covered}")
    tz = ZoneInfo(user.timezone)
    meals = await meals_on(session, user.id, today)
    if meals:
        lines.append("Meals today:")
        for meal in meals:
            at = meal.created_at.astimezone(tz).strftime("%H:%M")
            items = ", ".join(f"{i.name} {i.grams * meal.scale:.0f} g" for i in meal.items)
            lines.append(f"- {at} {meal.title} ({items}): {_m(meal.totals())}")

    days = await daily_stats(session, user.id, today - timedelta(days=LONG_DAYS - 1), today)
    recent = [d for d in days if d.day < today][-RECENT_DAYS:]
    lines.append("Previous 7 days (date: food; steps; water; workout sets):")
    for d in recent:
        food = _m(d.eaten) if d.eaten.kcal > 0 else "nothing logged"
        lines.append(f"- {d.day:%m-%d %a}: {food}; {d.steps} steps; {d.water_ml} ml; {d.sets} sets")
    week = _avg(recent)
    logged = sum(1 for d in recent if d.eaten.kcal > 0)
    if week:
        lines.append(f"7-day average on {logged} logged days: {_m(week)}.")
        if target:
            low_protein = sum(
                1 for d in recent if 0 < d.eaten.kcal and d.eaten.protein < target.protein * 0.9
            )
            over = sum(1 for d in recent if d.eaten.kcal > target.kcal * 1.1)
            under = sum(1 for d in recent if 0 < d.eaten.kcal < target.kcal * 0.8)
            lines.append(
                f"Of those days: protein under 90% of target on {low_protein}, "
                f"kcal over target by 10%+ on {over}, under 80% of target on {under}."
            )
    month = _avg(days[:-1])
    if month:
        logged_month = sum(1 for d in days[:-1] if d.eaten.kcal > 0)
        lines.append(f"28-day average on {logged_month} logged days: {_m(month)}.")
    steps = [d.steps for d in recent if d.steps]
    if steps:
        lines.append(f"Average steps on days with data: {sum(steps) / len(steps):.0f}.")

    since = today - timedelta(days=LONG_DAYS)
    weights = sorted(await weights_between(session, user.id, since, today))
    if len(weights) >= 2:
        (d0, w0), (d1, w1) = weights[0], weights[-1]
        weeks = max((d1 - d0).days / 7, 1 / 7)
        lines.append(
            f"Weight: {w0:.1f} kg on {d0:%m-%d} -> {w1:.1f} kg on {d1:%m-%d} "
            f"({w1 - w0:+.1f} kg, {(w1 - w0) / weeks:+.2f} kg/week), {len(weights)} weigh-ins."
        )
    else:
        lines.append("Weight trend: not enough weigh-ins in the last 28 days.")

    workouts = list(
        await session.scalars(
            select(Workout)
            .where(Workout.user_id == user.id, Workout.day > today - timedelta(days=WORKOUT_DAYS))
            .order_by(Workout.day)
        )
    )
    summaries = [s for s in await summarize(session, workouts) if s.sets]
    if summaries:
        lines.append(f"Workouts in the last {WORKOUT_DAYS} days:")
        for s in summaries:
            title = s.workout.title or "workout"
            lines.append(
                f"- {s.workout.day:%m-%d} {title}: {s.sets} sets, {s.exercises} exercises, "
                f"volume {s.volume_kg:.0f} kg"
            )
    else:
        lines.append(f"No workouts logged in the last {WORKOUT_DAYS} days.")

    titles = await session.scalars(
        select(func.lower(Meal.title)).where(
            Meal.user_id == user.id, Meal.day > today - timedelta(days=LONG_DAYS)
        )
    )
    frequent = Counter(titles).most_common(FREQUENT_FOODS)
    if frequent:
        lines.append(
            "Most frequent meals in 28 days: " + ", ".join(f"{t} x{n}" for t, n in frequent) + "."
        )
    return "<user_data>\n" + "\n".join(lines) + "\n</user_data>"
