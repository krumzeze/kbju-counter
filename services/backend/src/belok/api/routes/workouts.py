from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from belok.api.deps import ActiveUser, SessionDep
from belok.api.workout_schemas import (
    AnalyticsOut,
    CatalogDetailOut,
    CatalogItemOut,
    CustomExerciseIn,
    ExerciseOut,
    ExerciseRef,
    PlanItemIn,
    PreviousSetOut,
    ProgressOut,
    ProgressPointOut,
    ProgressSetOut,
    RecordsOut,
    SetCreatedOut,
    SetIn,
    SetOut,
    SetPatchIn,
    TemplateIn,
    TemplateItemOut,
    TemplateOut,
    TopExerciseOut,
    WeekOut,
    WorkoutExerciseOut,
    WorkoutOut,
    WorkoutPatchIn,
    WorkoutStartIn,
    WorkoutSummaryOut,
)
from belok.catalog import catalog
from belok.db.models import Exercise, User, Workout, WorkoutSet, WorkoutTemplate
from belok.domain.workouts import normalize_exercise
from belok.i18n import Language
from belok.services import workouts as svc

router = APIRouter(tags=["workouts"])


def _lang(user: User) -> Language:
    return user.language or Language.RU


def exercise_out(e: Exercise, lang: Language, sets: int = 0, last_day=None) -> ExerciseOut:
    return ExerciseOut(
        id=e.id,
        name=svc.title(e, lang),
        catalog_id=e.catalog_id,
        group=svc.group(e),
        cardio=e.cardio,
        sets=sets,
        last_day=last_day,
    )


def set_out(s: WorkoutSet, e: Exercise, lang: Language) -> SetOut:
    return SetOut(
        id=s.id,
        workout_id=s.workout_id,
        exercise_id=s.exercise_id,
        exercise=svc.title(e, lang),
        day=s.day,
        weight_kg=s.weight_kg,
        reps=s.reps,
        duration_s=s.duration_s,
    )


async def _resolve(session: AsyncSession, user: User, ref: ExerciseRef) -> Exercise:
    if ref.catalog_id is not None:
        item = catalog().get(ref.catalog_id)
        if item is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "exercise_not_found")
        return await svc.catalog_exercise(session, user.id, item)
    exercise = await svc.get_exercise(session, user.id, ref.exercise_id)
    if exercise is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exercise_not_found")
    return exercise


async def _workout(session: AsyncSession, user: User, workout_id: int) -> Workout:
    workout = await svc.get_workout(session, user.id, workout_id)
    if workout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workout_not_found")
    return workout


async def _workout_out(session: AsyncSession, user: User, workout: Workout) -> WorkoutOut:
    lang = _lang(user)
    sets = await svc.workout_sets(session, workout.id)
    order = [p["exercise_id"] for p in workout.plan]
    planned = {p["exercise_id"]: p.get("sets", 0) for p in workout.plan}
    for s in sets:
        if s.exercise_id not in planned:
            order.append(s.exercise_id)
            planned[s.exercise_id] = 0
    exercises = await svc.exercises_by_id(session, user.id, set(order))
    previous = await svc.previous_sets(session, user.id, workout, set(exercises))

    items = []
    for exercise_id in order:
        e = exercises.get(exercise_id)
        if e is None:
            continue
        before = previous.get(exercise_id, [])
        items.append(
            WorkoutExerciseOut(
                exercise=exercise_out(e, lang),
                planned_sets=planned[exercise_id],
                sets=[set_out(s, e, lang) for s in sets if s.exercise_id == exercise_id],
                previous=[
                    PreviousSetOut(weight_kg=s.weight_kg, reps=s.reps, duration_s=s.duration_s)
                    for s in before
                ],
                previous_day=before[0].day if before else None,
            )
        )
    return WorkoutOut(
        id=workout.id,
        day=workout.day,
        started_at=workout.started_at,
        finished_at=workout.finished_at,
        title=workout.title,
        exercises=items,
        sets=len(sets),
        volume_kg=sum(svc.set_volume(s) for s in sets),
    )


async def _template_out(
    session: AsyncSession, user: User, template: WorkoutTemplate
) -> TemplateOut:
    lang = _lang(user)
    exercises = await svc.exercises_by_id(
        session, user.id, {i["exercise_id"] for i in template.items}
    )
    return TemplateOut(
        id=template.id,
        name=template.name,
        items=[
            TemplateItemOut(
                exercise=exercise_out(exercises[i["exercise_id"]], lang), sets=i["sets"]
            )
            for i in template.items
            if i["exercise_id"] in exercises
        ],
    )


# Catalog


@router.get("/catalog")
async def get_catalog(user: ActiveUser, response: Response) -> list[CatalogItemOut]:
    response.headers["Cache-Control"] = "private, max-age=3600"
    lang = _lang(user)
    return [
        CatalogItemOut(
            id=x.id,
            name=x.title(lang),
            group=x.group,
            primary=x.primary,
            equipment=x.equipment,
            cardio=x.cardio,
            images=x.images,
        )
        for x in catalog().values()
    ]


@router.get("/catalog/{catalog_id}")
async def get_catalog_item(
    catalog_id: str, user: ActiveUser, session: SessionDep
) -> CatalogDetailOut:
    x = catalog().get(catalog_id)
    if x is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exercise_not_found")
    lang = _lang(user)
    exercise_id = await session.scalar(
        select(Exercise.id).where(Exercise.user_id == user.id, Exercise.catalog_id == x.id)
    )
    return CatalogDetailOut(
        id=x.id,
        name=x.title(lang),
        name_en=x.name["en"],
        group=x.group,
        primary=x.primary,
        secondary=x.secondary,
        equipment=x.equipment,
        cardio=x.cardio,
        images=x.images,
        instructions=x.steps(lang),
        level=x.level,
        mechanic=x.mechanic,
        force=x.force,
        exercise_id=exercise_id,
    )


# Exercises


@router.get("/exercises")
async def get_exercises(user: ActiveUser, session: SessionDep) -> list[ExerciseOut]:
    lang = _lang(user)
    return [
        exercise_out(s.exercise, lang, s.sets, s.last_day)
        for s in await svc.list_exercises(session, user.id)
    ]


@router.post("/exercises", status_code=status.HTTP_201_CREATED)
async def create_exercise(
    body: CustomExerciseIn, user: ActiveUser, session: SessionDep
) -> ExerciseOut:
    if not normalize_exercise(body.name):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "empty_exercise")
    exercise = await svc.custom_exercise(session, user.id, body.name, body.group, body.cardio)
    await session.commit()
    return exercise_out(exercise, _lang(user))


@router.post("/exercises/resolve")
async def resolve_exercise(body: ExerciseRef, user: ActiveUser, session: SessionDep) -> ExerciseOut:
    exercise = await _resolve(session, user, body)
    await session.commit()
    return exercise_out(exercise, _lang(user))


@router.get("/exercises/{exercise_id}/progress")
async def get_progress(
    exercise_id: int,
    user: ActiveUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 60,
) -> ProgressOut:
    exercise = await svc.get_exercise(session, user.id, exercise_id)
    if exercise is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exercise_not_found")
    points = []
    records = RecordsOut(e1rm=0, weight_kg=0, reps=0, volume_kg=0, duration_s=0)
    for day, sets in await svc.exercise_history(session, user.id, exercise.id, limit):
        top = max(sets, key=lambda s: (svc.set_e1rm(s), s.reps or 0))
        point = ProgressPointOut(
            day=day,
            top_weight_kg=top.weight_kg,
            top_reps=top.reps,
            e1rm=round(svc.set_e1rm(top), 1),
            sets=len(sets),
            reps=sum(s.reps or 0 for s in sets),
            volume_kg=sum(svc.set_volume(s) for s in sets),
            duration_s=sum(s.duration_s or 0 for s in sets),
            items=[
                ProgressSetOut(weight_kg=s.weight_kg, reps=s.reps, duration_s=s.duration_s)
                for s in sets
            ],
        )
        points.append(point)
        records = RecordsOut(
            e1rm=max(records.e1rm, point.e1rm),
            weight_kg=max(records.weight_kg, max(s.weight_kg for s in sets)),
            reps=max(records.reps, max(s.reps or 0 for s in sets)),
            volume_kg=max(records.volume_kg, point.volume_kg),
            duration_s=max(records.duration_s, point.duration_s),
        )
    return ProgressOut(exercise=exercise_out(exercise, _lang(user)), points=points, records=records)


# Workouts


@router.get("/workouts")
async def get_workouts(
    user: ActiveUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    before_id: int | None = None,
) -> list[WorkoutSummaryOut]:
    await svc.active_workout(session, user.id)
    summaries = await svc.recent_workouts(session, user.id, limit, before_id)
    lang = _lang(user)
    ids = {p["exercise_id"] for s in summaries for p in s.workout.plan}
    exercises = await svc.exercises_by_id(session, user.id, ids)
    await session.commit()
    return [
        WorkoutSummaryOut(
            id=s.workout.id,
            day=s.workout.day,
            started_at=s.workout.started_at,
            finished_at=s.workout.finished_at or s.last_set_at,
            title=s.workout.title,
            exercises=s.exercises,
            sets=s.sets,
            volume_kg=s.volume_kg,
            names=[
                svc.title(exercises[p["exercise_id"]], lang)
                for p in s.workout.plan
                if p["exercise_id"] in exercises
            ][:6],
        )
        for s in summaries
    ]


@router.get("/workouts/active")
async def get_active_workout(user: ActiveUser, session: SessionDep) -> WorkoutOut | None:
    workout = await svc.active_workout(session, user.id)
    await session.commit()
    return await _workout_out(session, user, workout) if workout else None


@router.post("/workouts", status_code=status.HTTP_201_CREATED)
async def start_workout(body: WorkoutStartIn, user: ActiveUser, session: SessionDep) -> WorkoutOut:
    title = body.title
    plan: list[dict] = []
    if body.template_id is not None:
        template = await svc.get_template(session, user.id, body.template_id)
        if template is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "template_not_found")
        title = title or template.name
        plan = [dict(i) for i in template.items]
    elif body.from_workout_id is not None:
        source = await _workout(session, user, body.from_workout_id)
        title = title or source.title
        plan = await _plan_of(session, user, source)
    workout = await svc.start_workout(session, user, title, plan)
    await session.commit()
    return await _workout_out(session, user, workout)


@router.get("/workouts/{workout_id}")
async def get_workout(workout_id: int, user: ActiveUser, session: SessionDep) -> WorkoutOut:
    return await _workout_out(session, user, await _workout(session, user, workout_id))


@router.patch("/workouts/{workout_id}")
async def patch_workout(
    workout_id: int, body: WorkoutPatchIn, user: ActiveUser, session: SessionDep
) -> WorkoutOut:
    workout = await _workout(session, user, workout_id)
    if "title" in body.model_fields_set:
        workout.title = body.title.strip() if body.title and body.title.strip() else None
    if body.finished:
        await svc.finish_workout(session, workout)
    await session.commit()
    return await _workout_out(session, user, workout)


@router.delete("/workouts/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workout(workout_id: int, user: ActiveUser, session: SessionDep) -> Response:
    await session.delete(await _workout(session, user, workout_id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/workouts/{workout_id}/exercises")
async def add_workout_exercise(
    workout_id: int, body: PlanItemIn, user: ActiveUser, session: SessionDep
) -> WorkoutOut:
    workout = await _workout(session, user, workout_id)
    exercise = await _resolve(session, user, body)
    svc.plan_add(workout, exercise.id, body.sets)
    await session.commit()
    return await _workout_out(session, user, workout)


@router.delete("/workouts/{workout_id}/exercises/{exercise_id}")
async def remove_workout_exercise(
    workout_id: int, exercise_id: int, user: ActiveUser, session: SessionDep
) -> WorkoutOut:
    workout = await _workout(session, user, workout_id)
    await svc.plan_remove(session, workout, exercise_id)
    await session.commit()
    return await _workout_out(session, user, workout)


@router.post("/workouts/{workout_id}/sets", status_code=status.HTTP_201_CREATED)
async def add_set(
    workout_id: int, body: SetIn, user: ActiveUser, session: SessionDep
) -> SetCreatedOut:
    workout = await _workout(session, user, workout_id)
    exercise = await svc.get_exercise(session, user.id, body.exercise_id)
    if exercise is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exercise_not_found")
    workout_set, record = await svc.add_set(
        session, workout, exercise, body.weight_kg, body.reps, body.duration_s
    )
    await session.commit()
    return SetCreatedOut(**set_out(workout_set, exercise, _lang(user)).model_dump(), record=record)


@router.patch("/sets/{set_id}")
async def patch_set(set_id: int, body: SetPatchIn, user: ActiveUser, session: SessionDep) -> SetOut:
    workout_set = await svc.get_set(session, user.id, set_id)
    if workout_set is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "set_not_found")
    if body.reps is None and body.duration_s is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reps_or_duration_required")
    workout_set.weight_kg = body.weight_kg
    workout_set.reps = body.reps
    workout_set.duration_s = body.duration_s
    await session.commit()
    exercise = await svc.get_exercise(session, user.id, workout_set.exercise_id)
    return set_out(workout_set, exercise, _lang(user))


@router.delete("/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_set(set_id: int, user: ActiveUser, session: SessionDep) -> Response:
    workout_set = await svc.get_set(session, user.id, set_id)
    if workout_set is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "set_not_found")
    await session.delete(workout_set)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Templates


@router.get("/templates")
async def get_templates(user: ActiveUser, session: SessionDep) -> list[TemplateOut]:
    return [
        await _template_out(session, user, t) for t in await svc.list_templates(session, user.id)
    ]


async def _template_items(session: AsyncSession, user: User, body: TemplateIn) -> list[dict]:
    if body.workout_id is not None:
        return await _plan_of(session, user, await _workout(session, user, body.workout_id))
    items = []
    for item in body.items:
        exercise = await _resolve(session, user, item)
        if all(i["exercise_id"] != exercise.id for i in items):
            items.append({"exercise_id": exercise.id, "sets": item.sets})
    return items


async def _plan_of(session: AsyncSession, user: User, workout: Workout) -> list[dict]:
    """The exercises of a workout as a plan, keeping as many sets as were done or planned."""
    out = await _workout_out(session, user, workout)
    return [
        {"exercise_id": e.exercise.id, "sets": max(len(e.sets), e.planned_sets) or 3}
        for e in out.exercises
    ]


@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def create_template(body: TemplateIn, user: ActiveUser, session: SessionDep) -> TemplateOut:
    template = WorkoutTemplate(
        user_id=user.id, name=body.name.strip(), items=await _template_items(session, user, body)
    )
    session.add(template)
    await session.commit()
    return await _template_out(session, user, template)


@router.put("/templates/{template_id}")
async def update_template(
    template_id: int, body: TemplateIn, user: ActiveUser, session: SessionDep
) -> TemplateOut:
    template = await svc.get_template(session, user.id, template_id)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "template_not_found")
    template.name = body.name.strip()
    template.items = await _template_items(session, user, body)
    await session.commit()
    return await _template_out(session, user, template)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_id: int, user: ActiveUser, session: SessionDep) -> Response:
    template = await svc.get_template(session, user.id, template_id)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "template_not_found")
    await session.delete(template)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Analytics


@router.get("/analytics")
async def get_analytics(
    user: ActiveUser, session: SessionDep, weeks: Annotated[int, Query(ge=4, le=52)] = 12
) -> AnalyticsOut:
    data = await svc.analytics(session, user, weeks)
    lang = _lang(user)
    return AnalyticsOut(
        weeks=[
            WeekOut(
                start=w.start,
                workouts=len(w.workouts),
                sets=w.sets,
                volume_kg=round(w.volume_kg),
                cardio_min=round(w.cardio_min),
            )
            for w in data.weeks
        ],
        streak_weeks=data.streak_weeks,
        total_workouts=data.total_workouts,
        muscles_week=data.muscles_week,
        muscles_month=data.muscles_month,
        groups_month=data.groups_month,
        top=[
            TopExerciseOut(exercise=exercise_out(e, lang), sets=n, best_e1rm=round(best, 1))
            for e, n, best in data.top
        ],
    )
