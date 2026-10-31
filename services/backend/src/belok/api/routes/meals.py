from collections.abc import Awaitable, Callable
from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from belok.api.deps import ActiveUser, AnalyzerDep, SessionDep, SettingsDep
from belok.api.schemas import DayOut, MealOut, MealPatchIn, SetOut, TextMealIn, macros_out
from belok.config import Settings
from belok.db.models import User
from belok.domain.nutrition import steps_kcal
from belok.i18n import Language
from belok.llm.analyzer import AnalysisError, AnalysisResult
from belok.services.meals import DailyLimitReached, analyze_meal, clamp_scale, ensure_within_limit
from belok.services.repo import day_summary, get_meal, meals_on, sets_on
from belok.timeutil import local_today

router = APIRouter(tags=["meals"])

MAX_PHOTO_BYTES = 10 * 1024 * 1024


@router.get("/day")
async def get_day(
    user: ActiveUser, session: SessionDep, day: Annotated[date | None, Query()] = None
) -> DayOut:
    day = day or local_today(user.timezone)
    summary = await day_summary(session, user, day)
    meals = await meals_on(session, user.id, day)
    sets = await sets_on(session, user.id, day)
    return DayOut(
        day=day,
        eaten=macros_out(summary.eaten),
        target=macros_out(summary.target),
        steps=summary.steps,
        steps_kcal=steps_kcal(summary.steps, summary.weight_kg or 70),
        weight_kg=summary.weight_kg,
        meals=[MealOut.of(m) for m in meals],
        sets=[
            SetOut(id=s.id, exercise=name, day=s.day, weight_kg=s.weight_kg, reps=s.reps)
            for s, name in sets
        ],
    )


@router.post("/meals/photo", status_code=status.HTTP_201_CREATED)
async def create_meal_from_photo(
    user: ActiveUser,
    session: SessionDep,
    settings: SettingsDep,
    analyzer: AnalyzerDep,
    photo: Annotated[UploadFile, File()],
    note: Annotated[str | None, Form(max_length=200)] = None,
) -> MealOut:
    if photo.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_image")
    image = await photo.read(MAX_PHOTO_BYTES + 1)
    if len(image) > MAX_PHOTO_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "image_too_large")
    return await _analyze(
        session, settings, user, "photo", lambda: analyzer.from_photo(image, note, _language(user))
    )


@router.post("/meals/text", status_code=status.HTTP_201_CREATED)
async def create_meal_from_text(
    body: TextMealIn,
    user: ActiveUser,
    session: SessionDep,
    settings: SettingsDep,
    analyzer: AnalyzerDep,
) -> MealOut:
    return await _analyze(
        session, settings, user, "text", lambda: analyzer.from_text(body.text, _language(user))
    )


@router.patch("/meals/{meal_id}")
async def patch_meal(
    meal_id: int, body: MealPatchIn, user: ActiveUser, session: SessionDep
) -> MealOut:
    meal = await get_meal(session, user.id, meal_id)
    if meal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "meal_not_found")
    meal.scale = clamp_scale(body.scale)
    await session.commit()
    return MealOut.of(meal)


@router.delete("/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(meal_id: int, user: ActiveUser, session: SessionDep) -> Response:
    meal = await get_meal(session, user.id, meal_id)
    if meal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "meal_not_found")
    await session.delete(meal)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _analyze(
    session: AsyncSession,
    settings: Settings,
    user: User,
    kind: str,
    call: Callable[[], Awaitable[AnalysisResult]],
) -> MealOut:
    try:
        await ensure_within_limit(session, user, settings.daily_analysis_limit)
    except DailyLimitReached as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "daily_limit") from exc
    try:
        meal = await analyze_meal(session, user, kind, call)
    except AnalysisError as exc:
        await session.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "analysis_failed") from exc
    await session.commit()
    if meal is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "no_food")
    return MealOut.of(meal)


def _language(user: User) -> Language:
    return user.language or Language.RU
