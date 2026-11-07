from collections.abc import Awaitable, Callable
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from belok.api.deps import (
    ActiveUser,
    AnalyzerDep,
    FoodDbDep,
    PhotosDep,
    SessionDep,
    SettingsDep,
    require,
)
from belok.api.routes.workouts import set_out
from belok.api.schemas import (
    BarcodeOut,
    DayOut,
    MacrosOut,
    ManualMealIn,
    MealHistoryOut,
    MealItemPatchIn,
    MealOut,
    MealPatchIn,
    ProductOut,
    RefineMealIn,
    TextMealIn,
    macros_out,
)
from belok.config import Settings
from belok.db.models import Meal, MealItem, User
from belok.domain.nutrition import water_target_ml
from belok.i18n import Language
from belok.images import BadImage, ImageTooLarge, media_type
from belok.llm.analyzer import AnalysisError, AnalysisResult
from belok.services.access import has_access
from belok.services.features import Feature
from belok.services.meals import (
    DailyLimitReached,
    analyze_meal,
    attach_photo,
    clamp_scale,
    copy_meal,
    ensure_within_limit,
    keep_for_eval,
    manual_meal,
    meal_analysis,
    meal_history,
    meal_photo_keys,
    photo_url,
    replace_items,
    resize_item,
    run_analysis,
)
from belok.services.photos import PhotoStore
from belok.services.products import (
    CODE_RE,
    ProductInfo,
    decode_barcode,
    find_product,
    remember_product,
)
from belok.services.repo import day_summary, get_meal, meals_on
from belok.services.targets import TargetSource
from belok.services.workouts import sets_on
from belok.timeutil import local_today, utcnow

router = APIRouter(tags=["meals"])

MAX_PHOTO_BYTES = 10 * 1024 * 1024


@router.get("/day")
async def get_day(
    user: ActiveUser,
    session: SessionDep,
    settings: SettingsDep,
    photos: PhotosDep,
    day: Annotated[date | None, Query()] = None,
) -> DayOut:
    day = day or local_today(user.timezone)
    summary = await day_summary(session, user, day)
    target = summary.target
    meals = await meals_on(session, user.id, day)
    sets = await sets_on(session, user.id, day)
    return DayOut(
        day=day,
        eaten=macros_out(summary.eaten),
        target=macros_out(target.macros) if target else None,
        target_source=target.source if target else None,
        adaptive_paused=bool(
            target
            and user.adaptive_target
            and has_access(user, utcnow())
            and target.source == TargetSource.FORMULA
        ),
        steps=summary.steps,
        water_ml=summary.water_ml,
        water_target_ml=water_target_ml(summary.weight_kg) if summary.weight_kg else None,
        activity_kcal=target.activity_kcal if target else 0.0,
        weight_kg=summary.weight_kg,
        meals=[_out(m, photos, settings) for m in meals],
        sets=[set_out(s, e, _language(user)) for s, e in sets],
    )


@router.post(
    "/meals/photo", status_code=status.HTTP_201_CREATED, dependencies=[require(Feature.PHOTO)]
)
async def create_meal_from_photo(
    user: ActiveUser,
    session: SessionDep,
    settings: SettingsDep,
    analyzer: AnalyzerDep,
    photos: PhotosDep,
    photo: Annotated[UploadFile, File()],
    note: Annotated[str | None, Form(max_length=200)] = None,
) -> MealOut:
    image, kind = await _read_photo(photo)
    meal = await _analyze(
        session,
        settings,
        user,
        "photo",
        lambda: analyzer.from_photo(image, kind, note, _language(user)),
    )
    if photos is not None:
        await attach_photo(photos, meal, image)
        await session.commit()
    return _out(meal, photos, settings)


@router.post(
    "/meals/text", status_code=status.HTTP_201_CREATED, dependencies=[require(Feature.TEXT)]
)
async def create_meal_from_text(
    body: TextMealIn,
    user: ActiveUser,
    session: SessionDep,
    settings: SettingsDep,
    analyzer: AnalyzerDep,
) -> MealOut:
    meal = await _analyze(
        session, settings, user, "text", lambda: analyzer.from_text(body.text, _language(user))
    )
    return MealOut.of(meal)


@router.post("/meals/manual", status_code=status.HTTP_201_CREATED)
async def create_manual_meal(body: ManualMealIn, user: ActiveUser, session: SessionDep) -> MealOut:
    per_100g = (body.kcal, body.protein, body.fat, body.carbs)
    meal = manual_meal(user, local_today(user.timezone), body.title, body.grams, per_100g)
    if body.barcode:
        meal.source = "barcode"
        label = ProductInfo(body.title, *per_100g, serving_g=body.grams)
        await remember_product(session, user.id, body.barcode, label)
    session.add(meal)
    await session.commit()
    return MealOut.of(meal)


@router.post("/barcode/photo", dependencies=[require(Feature.BARCODE)])
async def scan_barcode(
    user: ActiveUser,
    session: SessionDep,
    food_db: FoodDbDep,
    photo: Annotated[UploadFile, File()],
) -> BarcodeOut:
    image, _ = await _read_photo(photo)
    code = await decode_barcode(image)
    if code is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "no_barcode")
    return await _barcode(session, food_db, user, code)


@router.get("/barcode/{code}", dependencies=[require(Feature.BARCODE)])
async def get_barcode(
    code: str, user: ActiveUser, session: SessionDep, food_db: FoodDbDep
) -> BarcodeOut:
    if not CODE_RE.match(code):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_barcode")
    return await _barcode(session, food_db, user, code)


async def _barcode(session: AsyncSession, food_db: FoodDbDep, user: User, code: str) -> BarcodeOut:
    info = await find_product(session, food_db, user.id, code, _language(user))
    await session.commit()
    return BarcodeOut(code=code, product=ProductOut.model_validate(info) if info else None)


@router.get("/meals/history")
async def get_meal_history(
    user: ActiveUser,
    session: SessionDep,
    sort: Annotated[Literal["frequent", "recent"], Query()] = "frequent",
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[MealHistoryOut]:
    rows = await meal_history(session, user.id, sort == "frequent", limit)
    return [
        MealHistoryOut(
            meal_id=meal.id,
            title=meal.title,
            source=meal.source,
            times=times,
            last_eaten=meal.created_at,
            totals=MacrosOut.model_validate(meal.totals()),
        )
        for meal, times in rows
    ]


@router.post("/meals/{meal_id}/repeat", status_code=status.HTTP_201_CREATED)
async def repeat_meal(meal_id: int, user: ActiveUser, session: SessionDep) -> MealOut:
    meal = await get_meal(session, user.id, meal_id)
    if meal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "meal_not_found")
    copy = copy_meal(meal, local_today(user.timezone))
    session.add(copy)
    await session.commit()
    return MealOut.of(copy)


@router.patch("/meals/{meal_id}")
async def patch_meal(
    meal_id: int,
    body: MealPatchIn,
    user: ActiveUser,
    session: SessionDep,
    settings: SettingsDep,
    photos: PhotosDep,
) -> MealOut:
    meal = await get_meal(session, user.id, meal_id)
    if meal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "meal_not_found")
    meal.scale = clamp_scale(body.scale)
    await session.commit()
    return _out(meal, photos, settings)


@router.post("/meals/{meal_id}/refine")
async def refine_meal(
    meal_id: int,
    body: RefineMealIn,
    user: ActiveUser,
    session: SessionDep,
    settings: SettingsDep,
    analyzer: AnalyzerDep,
    photos: PhotosDep,
) -> MealOut:
    meal = await get_meal(session, user.id, meal_id)
    if meal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "meal_not_found")
    previous = meal_analysis(meal)
    await _ensure_within_limit(session, user, settings)
    try:
        analysis = await run_analysis(
            session,
            user,
            "refine",
            lambda: analyzer.refine(previous, body.text, _language(user)),
        )
    except AnalysisError as exc:
        await session.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "analysis_failed") from exc
    if not analysis.items:
        await session.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "no_food")
    await keep_for_eval(session, photos, user, meal)
    replace_items(meal, analysis)
    await session.commit()
    return _out(meal, photos, settings)


@router.patch("/meals/{meal_id}/items/{item_id}")
async def patch_meal_item(
    meal_id: int,
    item_id: int,
    body: MealItemPatchIn,
    user: ActiveUser,
    session: SessionDep,
    settings: SettingsDep,
    photos: PhotosDep,
) -> MealOut:
    meal, item = await _meal_item(session, user, meal_id, item_id)
    await keep_for_eval(session, photos, user, meal)
    resize_item(meal, item, body.grams)
    await session.commit()
    return _out(meal, photos, settings)


@router.delete("/meals/{meal_id}/items/{item_id}")
async def delete_meal_item(
    meal_id: int,
    item_id: int,
    user: ActiveUser,
    session: SessionDep,
    settings: SettingsDep,
    photos: PhotosDep,
) -> MealOut:
    meal, item = await _meal_item(session, user, meal_id, item_id)
    if len(meal.items) == 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "last_item")
    await keep_for_eval(session, photos, user, meal)
    meal.items.remove(item)
    await session.commit()
    return _out(meal, photos, settings)


async def _meal_item(
    session: AsyncSession, user: User, meal_id: int, item_id: int
) -> tuple[Meal, MealItem]:
    meal = await get_meal(session, user.id, meal_id)
    item = next((i for i in meal.items if i.id == item_id), None) if meal else None
    if meal is None or item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "meal_not_found")
    return meal, item


@router.delete("/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(
    meal_id: int, user: ActiveUser, session: SessionDep, photos: PhotosDep
) -> Response:
    meal = await get_meal(session, user.id, meal_id)
    if meal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "meal_not_found")
    keys = await meal_photo_keys(session, meal)
    await session.delete(meal)
    await session.commit()
    if photos is not None:
        await photos.delete_quietly(*keys)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _analyze(
    session: AsyncSession,
    settings: Settings,
    user: User,
    kind: str,
    call: Callable[[], Awaitable[AnalysisResult]],
) -> Meal:
    await _ensure_within_limit(session, user, settings)
    try:
        meal = await analyze_meal(session, user, kind, call)
    except AnalysisError as exc:
        await session.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "analysis_failed") from exc
    await session.commit()
    if meal is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "no_food")
    return meal


def _out(meal: Meal, photos: PhotoStore | None, settings: Settings) -> MealOut:
    return MealOut.of(meal, photo_url(photos, meal, settings.photo_retention_days))


async def _ensure_within_limit(session: AsyncSession, user: User, settings: Settings) -> None:
    try:
        await ensure_within_limit(session, user, settings)
    except DailyLimitReached as exc:
        if not exc.premium:
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "premium_required") from exc
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "daily_limit") from exc


async def _read_photo(photo: UploadFile) -> tuple[bytes, str]:
    """The image and its real type; the client's content type is only a first filter."""
    if photo.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_image")
    image = await photo.read(MAX_PHOTO_BYTES + 1)
    if len(image) > MAX_PHOTO_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "image_too_large")
    try:
        kind = media_type(image)
    except ImageTooLarge as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "image_too_large") from exc
    except BadImage as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_image") from exc
    return image, kind


def _language(user: User) -> Language:
    return user.language or Language.RU
