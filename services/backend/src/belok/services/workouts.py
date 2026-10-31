from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import case, delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from belok.catalog import MUSCLE_GROUP, CatalogExercise, Group, catalog, find_by_name
from belok.db.models import Exercise, User, Workout, WorkoutSet, WorkoutTemplate
from belok.domain.workouts import ParsedSet, estimated_1rm, normalize_exercise
from belok.i18n import Language
from belok.timeutil import local_today, utcnow

# An unfinished workout older than this is closed automatically.
STALE_AFTER = timedelta(hours=6)
MAX_PLAN = 30


def title(exercise: Exercise, lang: Language) -> str:
    item = catalog().get(exercise.catalog_id) if exercise.catalog_id else None
    return item.title(lang) if item else exercise.name


def group(exercise: Exercise) -> str | None:
    item = catalog().get(exercise.catalog_id) if exercise.catalog_id else None
    return item.group if item else exercise.group


def muscles(exercise: Exercise) -> tuple[list[str], list[str]]:
    item = catalog().get(exercise.catalog_id) if exercise.catalog_id else None
    if item:
        return item.primary, item.secondary
    if exercise.group:
        return [m for m, g in MUSCLE_GROUP.items() if g == exercise.group], []
    return [], []


def set_e1rm(s: WorkoutSet) -> float:
    return estimated_1rm(s.weight_kg, s.reps) if s.reps else 0.0


def set_volume(s: WorkoutSet) -> float:
    return s.weight_kg * s.reps if s.reps else 0.0


# Exercises


async def catalog_exercise(session: AsyncSession, user_id: int, item: CatalogExercise) -> Exercise:
    stmt = (
        insert(Exercise)
        .values(
            user_id=user_id,
            name=item.name["en"][:128],
            catalog_id=item.id,
            group=item.group,
            cardio=item.cardio,
        )
        .on_conflict_do_nothing(
            index_elements=["user_id", "catalog_id"], index_where=Exercise.catalog_id.isnot(None)
        )
    )
    await session.execute(stmt)
    return await session.scalar(
        select(Exercise).where(Exercise.user_id == user_id, Exercise.catalog_id == item.id)
    )


async def custom_exercise(
    session: AsyncSession, user_id: int, name: str, group: Group | None = None, cardio: bool = False
) -> Exercise:
    name = normalize_exercise(name)
    stmt = (
        insert(Exercise)
        .values(user_id=user_id, name=name, group=group, cardio=cardio)
        .on_conflict_do_nothing(
            index_elements=["user_id", "name"], index_where=Exercise.catalog_id.is_(None)
        )
    )
    await session.execute(stmt)
    return await session.scalar(
        select(Exercise).where(
            Exercise.user_id == user_id, Exercise.name == name, Exercise.catalog_id.is_(None)
        )
    )


async def find_exercise(session: AsyncSession, user_id: int, name: str) -> Exercise | None:
    custom = await session.scalar(
        select(Exercise).where(
            Exercise.user_id == user_id,
            Exercise.name == normalize_exercise(name),
            Exercise.catalog_id.is_(None),
        )
    )
    if custom or (item := find_by_name(name)) is None:
        return custom
    return await session.scalar(
        select(Exercise).where(Exercise.user_id == user_id, Exercise.catalog_id == item.id)
    )


async def exercise_by_text(session: AsyncSession, user_id: int, name: str) -> Exercise:
    """Free-text name from the bot: a catalog match in either language, else a custom one."""
    if exercise := await find_exercise(session, user_id, name):
        return exercise
    if item := find_by_name(name):
        return await catalog_exercise(session, user_id, item)
    return await custom_exercise(session, user_id, name)


async def get_exercise(session: AsyncSession, user_id: int, exercise_id: int) -> Exercise | None:
    return await session.scalar(
        select(Exercise).where(Exercise.id == exercise_id, Exercise.user_id == user_id)
    )


async def exercises_by_id(
    session: AsyncSession, user_id: int, ids: set[int]
) -> dict[int, Exercise]:
    if not ids:
        return {}
    result = await session.scalars(
        select(Exercise).where(Exercise.user_id == user_id, Exercise.id.in_(ids))
    )
    return {e.id: e for e in result}


@dataclass(slots=True)
class ExerciseStats:
    exercise: Exercise
    sets: int
    last_day: date | None


async def list_exercises(session: AsyncSession, user_id: int) -> list[ExerciseStats]:
    result = await session.execute(
        select(Exercise, func.count(WorkoutSet.id), func.max(WorkoutSet.day))
        .outerjoin(WorkoutSet, WorkoutSet.exercise_id == Exercise.id)
        .where(Exercise.user_id == user_id)
        .group_by(Exercise.id)
        .order_by(func.max(WorkoutSet.day).desc().nulls_last(), Exercise.id)
    )
    return [ExerciseStats(e, n, d) for e, n, d in result.all()]


# Workouts


async def get_workout(session: AsyncSession, user_id: int, workout_id: int) -> Workout | None:
    return await session.scalar(
        select(Workout).where(Workout.id == workout_id, Workout.user_id == user_id)
    )


async def _close(session: AsyncSession, workout: Workout) -> None:
    last = await session.scalar(
        select(func.max(WorkoutSet.created_at)).where(WorkoutSet.workout_id == workout.id)
    )
    workout.finished_at = last or workout.started_at


async def active_workout(session: AsyncSession, user_id: int) -> Workout | None:
    workout = await session.scalar(
        select(Workout)
        .where(Workout.user_id == user_id, Workout.finished_at.is_(None))
        .order_by(Workout.id.desc())
        .limit(1)
    )
    if workout and utcnow() - workout.started_at > STALE_AFTER:
        await _close(session, workout)
        return None
    return workout


async def start_workout(
    session: AsyncSession, user: User, title: str | None, plan: list[dict]
) -> Workout:
    workout = await active_workout(session, user.id)
    if workout:
        return workout
    workout = Workout(
        user_id=user.id, day=local_today(user.timezone), title=title, plan=plan[:MAX_PLAN]
    )
    session.add(workout)
    await session.flush()
    return workout


async def finish_workout(session: AsyncSession, workout: Workout) -> None:
    if workout.finished_at is None:
        workout.finished_at = utcnow()


async def workout_for_bot(session: AsyncSession, user: User) -> Workout:
    """Sets logged with /gym go to the open workout, else today's latest one, else a new one."""
    workout = await active_workout(session, user.id)
    if workout:
        return workout
    today = local_today(user.timezone)
    workout = await session.scalar(
        select(Workout)
        .where(Workout.user_id == user.id, Workout.day == today)
        .order_by(Workout.id.desc())
        .limit(1)
    )
    if workout is None:
        workout = Workout(user_id=user.id, day=today, plan=[], finished_at=utcnow())
        session.add(workout)
        await session.flush()
    return workout


def plan_add(workout: Workout, exercise_id: int, sets: int) -> None:
    if any(p["exercise_id"] == exercise_id for p in workout.plan) or len(workout.plan) >= MAX_PLAN:
        return
    workout.plan = [*workout.plan, {"exercise_id": exercise_id, "sets": sets}]


async def plan_remove(session: AsyncSession, workout: Workout, exercise_id: int) -> None:
    workout.plan = [p for p in workout.plan if p["exercise_id"] != exercise_id]
    await session.execute(
        delete(WorkoutSet).where(
            WorkoutSet.workout_id == workout.id, WorkoutSet.exercise_id == exercise_id
        )
    )


async def add_set(
    session: AsyncSession,
    workout: Workout,
    exercise: Exercise,
    weight_kg: float,
    reps: int | None,
    duration_s: int | None,
) -> tuple[WorkoutSet, bool]:
    """Returns the set and whether it beats the previous best estimated 1RM."""
    previous_best = 0.0
    if reps:
        previous_best = await best_e1rm(session, exercise.id)
    workout_set = WorkoutSet(
        user_id=workout.user_id,
        workout_id=workout.id,
        exercise_id=exercise.id,
        day=workout.day,
        weight_kg=weight_kg,
        reps=reps,
        duration_s=duration_s,
    )
    session.add(workout_set)
    plan_add(workout, exercise.id, 0)
    await session.flush()
    record = previous_best > 0 and weight_kg > 0 and set_e1rm(workout_set) > previous_best
    return workout_set, record


async def add_parsed_sets(
    session: AsyncSession, workout: Workout, exercise: Exercise, sets: list[ParsedSet]
) -> None:
    session.add_all(
        WorkoutSet(
            user_id=workout.user_id,
            workout_id=workout.id,
            exercise_id=exercise.id,
            day=workout.day,
            weight_kg=s.weight_kg,
            reps=s.reps,
        )
        for s in sets
    )
    plan_add(workout, exercise.id, 0)


E1RM_SQL = case(
    (WorkoutSet.reps > 1, WorkoutSet.weight_kg * (1 + WorkoutSet.reps / 30.0)),
    else_=WorkoutSet.weight_kg,
)


async def best_e1rm(session: AsyncSession, exercise_id: int) -> float:
    value = await session.scalar(
        select(func.max(E1RM_SQL)).where(
            WorkoutSet.exercise_id == exercise_id, WorkoutSet.reps.isnot(None)
        )
    )
    return value or 0.0


async def get_set(session: AsyncSession, user_id: int, set_id: int) -> WorkoutSet | None:
    return await session.scalar(
        select(WorkoutSet).where(WorkoutSet.id == set_id, WorkoutSet.user_id == user_id)
    )


async def workout_sets(session: AsyncSession, workout_id: int) -> list[WorkoutSet]:
    result = await session.scalars(
        select(WorkoutSet).where(WorkoutSet.workout_id == workout_id).order_by(WorkoutSet.id)
    )
    return list(result)


async def previous_sets(
    session: AsyncSession, user_id: int, workout: Workout, exercise_ids: set[int]
) -> dict[int, list[WorkoutSet]]:
    """Sets from the most recent earlier workout for each exercise."""
    if not exercise_ids:
        return {}
    latest = (
        select(WorkoutSet.exercise_id, func.max(WorkoutSet.workout_id))
        .where(
            WorkoutSet.user_id == user_id,
            WorkoutSet.exercise_id.in_(exercise_ids),
            WorkoutSet.workout_id < workout.id,
        )
        .group_by(WorkoutSet.exercise_id)
    )
    pairs = [tuple(row) for row in (await session.execute(latest)).all()]
    if not pairs:
        return {}
    result = await session.scalars(
        select(WorkoutSet)
        .where(tuple_(WorkoutSet.exercise_id, WorkoutSet.workout_id).in_(pairs))
        .order_by(WorkoutSet.id)
    )
    by_exercise: dict[int, list[WorkoutSet]] = defaultdict(list)
    for s in result:
        by_exercise[s.exercise_id].append(s)
    return by_exercise


@dataclass(slots=True)
class WorkoutSummary:
    workout: Workout
    sets: int
    exercises: int
    volume_kg: float
    last_set_at: datetime | None


async def recent_workouts(
    session: AsyncSession, user_id: int, limit: int, before_id: int | None
) -> list[WorkoutSummary]:
    query = select(Workout).where(Workout.user_id == user_id)
    if before_id:
        query = query.where(Workout.id < before_id)
    workouts = list(await session.scalars(query.order_by(Workout.id.desc()).limit(limit)))
    if not workouts:
        return []
    stats = await session.execute(
        select(
            WorkoutSet.workout_id,
            func.count(),
            func.count(func.distinct(WorkoutSet.exercise_id)),
            func.coalesce(func.sum(WorkoutSet.weight_kg * WorkoutSet.reps), 0),
            func.max(WorkoutSet.created_at),
        )
        .where(WorkoutSet.workout_id.in_([w.id for w in workouts]))
        .group_by(WorkoutSet.workout_id)
    )
    by_id = {row[0]: row[1:] for row in stats.all()}
    return [WorkoutSummary(w, *by_id.get(w.id, (0, 0, 0.0, None))) for w in workouts]


# Templates


async def list_templates(session: AsyncSession, user_id: int) -> list[WorkoutTemplate]:
    result = await session.scalars(
        select(WorkoutTemplate)
        .where(WorkoutTemplate.user_id == user_id)
        .order_by(WorkoutTemplate.id)
    )
    return list(result)


async def get_template(
    session: AsyncSession, user_id: int, template_id: int
) -> WorkoutTemplate | None:
    return await session.scalar(
        select(WorkoutTemplate).where(
            WorkoutTemplate.id == template_id, WorkoutTemplate.user_id == user_id
        )
    )


# History and analytics


async def exercise_history(
    session: AsyncSession, user_id: int, exercise_id: int, limit: int
) -> list[tuple[date, list[WorkoutSet]]]:
    days = (
        await session.scalars(
            select(WorkoutSet.day)
            .where(WorkoutSet.user_id == user_id, WorkoutSet.exercise_id == exercise_id)
            .group_by(WorkoutSet.day)
            .order_by(WorkoutSet.day.desc())
            .limit(limit)
        )
    ).all()
    if not days:
        return []
    sets = await session.scalars(
        select(WorkoutSet)
        .where(
            WorkoutSet.user_id == user_id,
            WorkoutSet.exercise_id == exercise_id,
            WorkoutSet.day.in_(days),
        )
        .order_by(WorkoutSet.day, WorkoutSet.id)
    )
    by_day: dict[date, list[WorkoutSet]] = defaultdict(list)
    for s in sets:
        by_day[s.day].append(s)
    return sorted(by_day.items())


@dataclass(slots=True)
class Week:
    start: date
    workouts: set[int] = field(default_factory=set)
    sets: int = 0
    volume_kg: float = 0.0
    cardio_min: float = 0.0


@dataclass(slots=True)
class Analytics:
    weeks: list[Week]
    streak_weeks: int
    total_workouts: int
    muscles_week: dict[str, float]
    muscles_month: dict[str, float]
    groups_month: dict[str, int]
    top: list[tuple[Exercise, int, float]]


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


async def analytics(session: AsyncSession, user: User, weeks: int) -> Analytics:
    today = local_today(user.timezone)
    first = week_start(today) - timedelta(weeks=weeks - 1)
    rows = (
        await session.execute(
            select(WorkoutSet, Exercise)
            .join(Exercise)
            .where(WorkoutSet.user_id == user.id, WorkoutSet.day >= first)
        )
    ).all()

    by_week = {first + timedelta(weeks=i): Week(first + timedelta(weeks=i)) for i in range(weeks)}
    muscles_week: dict[str, float] = defaultdict(float)
    muscles_month: dict[str, float] = defaultdict(float)
    groups_month: dict[str, int] = defaultdict(int)
    top: dict[int, list] = {}
    month_start = today - timedelta(days=29)
    this_week = week_start(today)
    for s, exercise in rows:
        week = by_week.get(week_start(s.day))
        if week is None:
            continue
        week.workouts.add(s.workout_id)
        week.sets += 1
        week.volume_kg += set_volume(s)
        week.cardio_min += (s.duration_s or 0) / 60
        if s.day < month_start:
            continue
        primary, secondary = muscles(exercise)
        for target, start in ((muscles_month, month_start), (muscles_week, this_week)):
            if s.day < start:
                continue
            for m in primary:
                target[m] += 1
            for m in secondary:
                target[m] += 0.5
        if g := group(exercise):
            groups_month[g] += 1
        entry = top.setdefault(exercise.id, [exercise, 0, 0.0])
        entry[1] += 1
        entry[2] = max(entry[2], set_e1rm(s))

    days = await session.scalars(
        select(WorkoutSet.day).where(WorkoutSet.user_id == user.id).distinct()
    )
    week_starts = {week_start(d) for d in days}
    streak = 0
    cursor = this_week if this_week in week_starts else this_week - timedelta(weeks=1)
    while cursor in week_starts:
        streak += 1
        cursor -= timedelta(weeks=1)

    total = await session.scalar(
        select(func.count(func.distinct(WorkoutSet.workout_id))).where(
            WorkoutSet.user_id == user.id
        )
    )
    ranked = sorted(top.values(), key=lambda e: e[1], reverse=True)[:8]
    return Analytics(
        weeks=list(by_week.values()),
        streak_weeks=streak,
        total_workouts=total or 0,
        muscles_week=dict(muscles_week),
        muscles_month=dict(muscles_month),
        groups_month=dict(groups_month),
        top=[(e, n, best) for e, n, best in ranked],
    )


async def sets_on(
    session: AsyncSession, user_id: int, day: date
) -> list[tuple[WorkoutSet, Exercise]]:
    result = await session.execute(
        select(WorkoutSet, Exercise)
        .join(Exercise)
        .where(WorkoutSet.user_id == user_id, WorkoutSet.day == day)
        .order_by(WorkoutSet.id)
    )
    return [(s, e) for s, e in result.all()]
