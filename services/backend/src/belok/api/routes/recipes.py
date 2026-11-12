import asyncio
import logging
from html import escape
from typing import Annotated

from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from belok.api.deps import (
    ActiveUser,
    AdminUser,
    AnalyzerDep,
    BotDep,
    PhotosDep,
    SessionDep,
    SettingsDep,
    refresh_day_card_later,
    require,
)
from belok.api.recipe_schemas import (
    AdminRecipeOut,
    DiaryIn,
    IngredientsIn,
    PhotoUploadOut,
    PublishIn,
    RatingIn,
    RecipeCardOut,
    RecipeIn,
    RecipeItemOut,
    RecipeOut,
    RecipeRef,
    RejectIn,
    StepOut,
)
from belok.api.routes.meals import _ensure_within_limit, _language, _read_photo
from belok.api.schemas import MacrosOut, MealOut
from belok.bot.texts import t
from belok.db.models import Recipe, RecipeFavorite, RecipeRating, User
from belok.db.models import RecipeStatus as Status
from belok.domain.nutrition import Macros
from belok.i18n import Language
from belok.llm.analyzer import AnalysisError
from belok.services import recipes
from belok.services.audit import log_action
from belok.services.features import Feature
from belok.services.meals import run_analysis
from belok.services.notify import notify_admins
from belok.services.photos import PhotoStore, make_thumbnail, recipe_key
from belok.services.recipes import Filter, ItemData, RecipeError, Scope, Stats
from belok.services.repo import day_summary
from belok.services.widgets import send_recipe
from belok.timeutil import local_today

log = logging.getLogger(__name__)

router = APIRouter(tags=["recipes"])

NOT_FOUND = {"recipe_not_found"}


def _fail(exc: RecipeError) -> HTTPException:
    code = (
        status.HTTP_404_NOT_FOUND
        if exc.code in NOT_FOUND
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    return HTTPException(code, exc.code)


def _url(photos: PhotoStore | None, key: str | None) -> str | None:
    return photos.url(key) if photos and key else None


def _card_fields(recipe: Recipe, user: User, s: Stats, photos: PhotoStore | None) -> dict:
    return {
        "id": recipe.id,
        "title": recipe.title,
        "status": recipe.status,
        "portions": recipe.portions,
        "per_portion": MacrosOut.model_validate(recipes.per_portion(recipe)),
        "photo_url": _url(photos, recipe.photo_key),
        "author_name": recipe.author_name,
        "is_mine": recipe.owner_id == user.id,
        "is_favorite": s.is_favorite,
        "favorites": s.favorites,
        "rating": round(s.rating, 1) if s.rating is not None else None,
        "ratings": s.ratings,
        "cooked": s.cooked,
    }


async def _cards(
    session: AsyncSession, user: User, items: list[Recipe], photos: PhotoStore | None
) -> list[RecipeCardOut]:
    st = await recipes.stats(session, user, [r.id for r in items])
    return [RecipeCardOut(**_card_fields(r, user, st[r.id], photos)) for r in items]


async def _detail_fields(
    session: AsyncSession, user: User, recipe: Recipe, photos: PhotoStore | None
) -> dict:
    s = (await recipes.stats(session, user, [recipe.id]))[recipe.id]
    parent = await session.get(Recipe, recipe.forked_from_id) if recipe.forked_from_id else None
    if parent is not None and not recipes.can_view(parent, user):
        parent = None
    return {
        **_card_fields(recipe, user, s, photos),
        "cooked_grams": recipe.cooked_grams,
        "raw_grams": recipe.raw_grams(),
        "totals": MacrosOut.model_validate(recipe.totals()),
        "items": [
            RecipeItemOut(
                name=i.name, grams=i.grams, kcal=i.kcal, protein=i.protein, fat=i.fat, carbs=i.carbs
            )
            for i in recipe.items
        ],
        "steps": [
            StepOut(text=st["text"], photo=st.get("photo"), photo_url=_url(photos, st.get("photo")))
            for st in recipe.steps
        ],
        "photo": recipe.photo_key,
        "reject_reason": recipe.reject_reason if recipe.owner_id == user.id else None,
        "forked_from": RecipeRef(id=parent.id, title=parent.title) if parent else None,
        "my_rating": s.my_rating,
        "can_rate": recipe.owner_id != user.id
        and recipe.status == Status.PUBLIC
        and s.cooked_by_me,
        "created_at": recipe.created_at,
    }


async def _out(
    session: AsyncSession, user: User, recipe: Recipe, photos: PhotoStore | None
) -> RecipeOut:
    return RecipeOut(**await _detail_fields(session, user, recipe, photos))


async def _remaining(session: AsyncSession, user: User) -> Macros | None:
    summary = await day_summary(session, user, local_today(user.timezone))
    if summary.target is None:
        return None
    target, eaten = summary.target.macros, summary.eaten
    return Macros(
        target.kcal - eaten.kcal,
        target.protein - eaten.protein,
        target.fat - eaten.fat,
        target.carbs - eaten.carbs,
    )


@router.get("/recipes")
async def list_recipes(
    user: ActiveUser,
    session: SessionDep,
    photos: PhotosDep,
    scope: Scope = Scope.CATALOG,
    q: Annotated[str | None, Query(max_length=100)] = None,
    filters: Annotated[list[Filter] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RecipeCardOut]:
    chosen = set(filters or [])
    remaining = await _remaining(session, user) if Filter.FITS in chosen else None
    found = await recipes.search(
        session,
        user,
        scope,
        q,
        chosen,
        remaining.kcal if remaining else None,
        limit,
        offset,
    )
    return await _cards(session, user, found, photos)


@router.get("/recipes/suggestions")
async def recipe_suggestions(
    user: ActiveUser, session: SessionDep, photos: PhotosDep
) -> list[RecipeCardOut]:
    remaining = await _remaining(session, user)
    if remaining is None:
        return []
    return await _cards(session, user, await recipes.suggestions(session, user, remaining), photos)


@router.post("/recipes/photos", status_code=status.HTTP_201_CREATED)
async def upload_recipe_photo(
    user: ActiveUser,
    photos: PhotosDep,
    photo: Annotated[UploadFile, File()],
) -> PhotoUploadOut:
    if photos is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "photos_unavailable")
    image, _ = await _read_photo(photo)
    try:
        thumb = await asyncio.to_thread(make_thumbnail, image)
    except Exception as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_image") from exc
    key = recipe_key(user.id)
    await photos.put(key, thumb)
    return PhotoUploadOut(photo=key, photo_url=photos.url(key))


@router.post("/recipes/ingredients", dependencies=[require(Feature.TEXT)])
async def parse_ingredients(
    body: IngredientsIn,
    user: ActiveUser,
    session: SessionDep,
    settings: SettingsDep,
    analyzer: AnalyzerDep,
) -> list[RecipeItemOut]:
    await _ensure_within_limit(session, user, settings)
    try:
        analysis = await run_analysis(
            session, user, "text", lambda: analyzer.from_text(body.text, _language(user))
        )
    except AnalysisError as exc:
        await session.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "analysis_failed") from exc
    await session.commit()
    if not analysis.items:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "no_food")
    return [RecipeItemOut(**i.model_dump()) for i in analysis.items if i.grams > 0]


def _check_keys(user: User, body: RecipeIn, recipe: Recipe | None) -> None:
    own = f"recipes/{user.id}/"
    allowed = set(recipe.photo_keys()) if recipe else set()
    for key in [body.photo, *(s.photo for s in body.steps)]:
        if key and not key.startswith(own) and key not in allowed:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_photo")


def _apply(recipe: Recipe, body: RecipeIn) -> list[str]:
    return recipes.apply(
        recipe,
        body.title,
        body.portions,
        body.cooked_grams,
        [ItemData(**i.model_dump()) for i in body.items],
        [{"text": s.text, "photo": s.photo} for s in body.steps],
        body.photo,
    )


@router.post("/recipes", status_code=status.HTTP_201_CREATED)
async def create_recipe(
    body: RecipeIn, user: ActiveUser, session: SessionDep, photos: PhotosDep
) -> RecipeOut:
    _check_keys(user, body, None)
    recipe = Recipe(owner_id=user.id, status=Status.PRIVATE, steps=[])
    _apply(recipe, body)
    session.add(recipe)
    await session.commit()
    return await _out(session, user, recipe, photos)


@router.get("/recipes/{recipe_id}")
async def get_recipe(
    recipe_id: int, user: ActiveUser, session: SessionDep, photos: PhotosDep
) -> RecipeOut:
    try:
        recipe = await recipes.get_visible(session, user, recipe_id)
    except RecipeError as exc:
        raise _fail(exc) from exc
    return await _out(session, user, recipe, photos)


@router.put("/recipes/{recipe_id}")
async def update_recipe(
    recipe_id: int,
    body: RecipeIn,
    user: ActiveUser,
    session: SessionDep,
    photos: PhotosDep,
    bot: BotDep,
) -> RecipeOut:
    try:
        recipe = await recipes.get_own(session, user, recipe_id)
    except RecipeError as exc:
        raise _fail(exc) from exc
    _check_keys(user, body, recipe)
    was_public = recipe.status == Status.PUBLIC
    unused = _apply(recipe, body)
    recipes.resubmit_after_edit(recipe, user)
    await session.commit()
    if photos is not None and unused:
        await photos.delete_quietly(*unused)
    if was_public and recipe.status == Status.PENDING:
        await _announce(bot, session, recipe, user)
    return await _out(session, user, recipe, photos)


@router.delete("/recipes/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(
    recipe_id: int, user: ActiveUser, session: SessionDep, photos: PhotosDep
) -> Response:
    recipe = await session.get(Recipe, recipe_id)
    if recipe is None or (recipe.owner_id != user.id and not user.is_admin):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "recipe_not_found")
    keys = recipe.photo_keys()
    await session.delete(recipe)
    await session.commit()
    if photos is not None and keys:
        await photos.delete_quietly(*keys)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/recipes/{recipe_id}/fork", status_code=status.HTTP_201_CREATED)
async def fork_recipe(
    recipe_id: int, user: ActiveUser, session: SessionDep, photos: PhotosDep
) -> RecipeOut:
    try:
        recipe = await recipes.get_visible(session, user, recipe_id)
    except RecipeError as exc:
        raise _fail(exc) from exc
    copy = recipes.fork(recipe, user)
    session.add(copy)
    await session.commit()
    return await _out(session, user, copy, photos)


@router.put("/recipes/{recipe_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
async def add_favorite(recipe_id: int, user: ActiveUser, session: SessionDep) -> Response:
    try:
        await recipes.get_visible(session, user, recipe_id)
    except RecipeError as exc:
        raise _fail(exc) from exc
    if await session.get(RecipeFavorite, (user.id, recipe_id)) is None:
        session.add(RecipeFavorite(user_id=user.id, recipe_id=recipe_id))
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/recipes/{recipe_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(recipe_id: int, user: ActiveUser, session: SessionDep) -> Response:
    await session.execute(
        delete(RecipeFavorite).where(
            RecipeFavorite.user_id == user.id, RecipeFavorite.recipe_id == recipe_id
        )
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/recipes/{recipe_id}/rating")
async def rate_recipe(
    recipe_id: int, body: RatingIn, user: ActiveUser, session: SessionDep, photos: PhotosDep
) -> RecipeOut:
    try:
        recipe = await recipes.get_visible(session, user, recipe_id)
    except RecipeError as exc:
        raise _fail(exc) from exc
    if not await recipes.can_rate(session, user, recipe):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cook_first")
    rating = await session.get(RecipeRating, (user.id, recipe_id))
    if rating is None:
        session.add(RecipeRating(user_id=user.id, recipe_id=recipe_id, stars=body.stars))
    else:
        rating.stars = body.stars
    await session.commit()
    return await _out(session, user, recipe, photos)


@router.post(
    "/recipes/{recipe_id}/diary",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(refresh_day_card_later)],
)
async def add_to_diary(
    recipe_id: int, body: DiaryIn, user: ActiveUser, session: SessionDep
) -> MealOut:
    try:
        recipe = await recipes.get_visible(session, user, recipe_id)
        meal = recipes.to_meal(
            recipe,
            user,
            local_today(user.timezone),
            body.items,
            body.portions if body.mode == "portions" else None,
            body.grams if body.mode == "grams" else None,
            body.cooked_grams,
        )
    except RecipeError as exc:
        raise _fail(exc) from exc
    session.add(meal)
    await session.commit()
    return MealOut.of(meal)


@router.post("/recipes/{recipe_id}/cook", status_code=status.HTTP_204_NO_CONTENT)
async def cook_in_chat(
    recipe_id: int,
    user: ActiveUser,
    session: SessionDep,
    settings: SettingsDep,
    bot: BotDep,
) -> Response:
    try:
        recipe = await recipes.get_visible(session, user, recipe_id)
    except RecipeError as exc:
        raise _fail(exc) from exc
    if not await send_recipe(bot, session, user, recipe, settings.webapp_url):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "widget_unavailable")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/recipes/{recipe_id}/publish")
async def publish_recipe(
    recipe_id: int,
    body: PublishIn,
    user: ActiveUser,
    session: SessionDep,
    photos: PhotosDep,
    bot: BotDep,
) -> RecipeOut:
    try:
        recipe = await recipes.get_own(session, user, recipe_id)
        recipes.submit(recipe, user, body.author_name)
    except RecipeError as exc:
        raise _fail(exc) from exc
    await session.commit()
    if recipe.status == Status.PENDING:
        await _announce(bot, session, recipe, user)
    return await _out(session, user, recipe, photos)


async def _announce(bot, session: AsyncSession, recipe: Recipe, user: User) -> None:
    name = escape(recipe.author_name or user.first_name or str(user.id))
    text = f"📝 Рецепт на модерации: «{escape(recipe.title)}» от {name}"
    try:
        await notify_admins(bot, session, "recipes", text)
    except Exception:
        log.warning("failed to announce recipe %s", recipe.id, exc_info=True)


@router.get("/admin/recipes")
async def admin_recipes(
    admin: AdminUser,
    session: SessionDep,
    photos: PhotosDep,
    status_: Annotated[Status, Query(alias="status")] = Status.PENDING,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AdminRecipeOut]:
    rows = await session.scalars(
        select(Recipe)
        .where(Recipe.status == status_)
        .order_by(Recipe.updated_at.desc())
        .limit(limit)
    )
    out = []
    for recipe in rows.all():
        owner = await session.get(User, recipe.owner_id)
        out.append(
            AdminRecipeOut(
                **await _detail_fields(session, admin, recipe, photos),
                owner_id=recipe.owner_id,
                owner_name=(owner.first_name or owner.username) if owner else None,
                warnings=recipes.plausibility(recipe),
            )
        )
    return out


async def _moderated(session: AsyncSession, bot, recipe: Recipe, key: str, **kwargs: str) -> None:
    owner = await session.get(User, recipe.owner_id)
    if owner is None or owner.bot_blocked:
        return
    lang = owner.language or Language.RU
    try:
        await bot.send_message(owner.id, t(lang, key, title=escape(recipe.title), **kwargs))
    except TelegramAPIError:
        log.warning("failed to tell %s about recipe %s", owner.id, recipe.id, exc_info=True)


@router.post("/admin/recipes/{recipe_id}/approve")
async def approve_recipe(
    recipe_id: int, admin: AdminUser, session: SessionDep, photos: PhotosDep, bot: BotDep
) -> RecipeOut:
    recipe = await session.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "recipe_not_found")
    recipes.approve(recipe)
    log_action(session, admin, "approve_recipe", recipe.owner_id, recipe_id=recipe.id)
    await session.commit()
    await _moderated(session, bot, recipe, "recipe_approved")
    return await _out(session, admin, recipe, photos)


@router.post("/admin/recipes/{recipe_id}/reject")
async def reject_recipe(
    recipe_id: int,
    body: RejectIn,
    admin: AdminUser,
    session: SessionDep,
    photos: PhotosDep,
    bot: BotDep,
) -> RecipeOut:
    recipe = await session.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "recipe_not_found")
    recipes.reject(recipe, body.reason)
    log_action(session, admin, "reject_recipe", recipe.owner_id, recipe_id=recipe.id)
    await session.commit()
    await _moderated(session, bot, recipe, "recipe_rejected", reason=escape(body.reason))
    return await _out(session, admin, recipe, photos)
