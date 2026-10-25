from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from belok.api.deps import ActiveUser, SessionDep
from belok.api.schemas import ProgressOut, ProgressPointOut, SetOut, WorkoutIn
from belok.domain.workouts import ParsedSet, estimated_1rm, normalize_exercise
from belok.services.repo import (
    add_sets,
    exercise_history,
    get_or_create_exercise,
    get_set,
    list_exercises,
    sets_on,
)
from belok.timeutil import local_today

router = APIRouter(tags=["workouts"])


@router.get("/exercises")
async def get_exercises(user: ActiveUser, session: SessionDep) -> list[str]:
    return await list_exercises(session, user.id)


@router.post("/workouts", status_code=status.HTTP_201_CREATED)
async def create_sets(body: WorkoutIn, user: ActiveUser, session: SessionDep) -> list[SetOut]:
    name = normalize_exercise(body.exercise)
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "empty_exercise")
    today = local_today(user.timezone)
    exercise = await get_or_create_exercise(session, user.id, name)
    await add_sets(
        session, user.id, exercise, today, [ParsedSet(s.weight_kg, s.reps) for s in body.sets]
    )
    await session.commit()
    return [
        SetOut(id=s.id, exercise=n, day=s.day, weight_kg=s.weight_kg, reps=s.reps)
        for s, n in await sets_on(session, user.id, today)
    ]


@router.delete("/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_set(set_id: int, user: ActiveUser, session: SessionDep) -> Response:
    workout_set = await get_set(session, user.id, set_id)
    if workout_set is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "set_not_found")
    await session.delete(workout_set)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/progress")
async def get_progress(
    user: ActiveUser,
    session: SessionDep,
    exercise: Annotated[str, Query(min_length=1, max_length=128)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ProgressOut:
    name = normalize_exercise(exercise)
    points = []
    for day, sets in await exercise_history(session, user.id, name, limit):
        top = max(sets, key=lambda s: estimated_1rm(s.weight_kg, s.reps))
        points.append(
            ProgressPointOut(
                day=day,
                top_weight_kg=top.weight_kg,
                top_reps=top.reps,
                e1rm=round(estimated_1rm(top.weight_kg, top.reps), 1),
                sets=len(sets),
            )
        )
    return ProgressOut(exercise=name, points=points)
