"""Recipes: own and public ones, forks, favorites, ratings, moderation and logging to the diary."""

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import Meal, MealItem, Recipe, RecipeFavorite, RecipeItem, RecipeRating, User
from belok.db.models import RecipeStatus as Status
from belok.domain.nutrition import Macros
from belok.timeutil import utcnow

PROTEIN_SHARE = 0.3
LIGHT_KCAL = 400
SUGGESTIONS = 6


class Scope(StrEnum):
    CATALOG = "catalog"
    MINE = "mine"
    FAVORITES = "favorites"


class Filter(StrEnum):
    PROTEIN = "protein"
    LIGHT = "light"
    FITS = "fits"


class RecipeError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class Stats:
    favorites: int = 0
    rating: float | None = None
    ratings: int = 0
    cooked: int = 0
    is_favorite: bool = False
    my_rating: int | None = None
    cooked_by_me: bool = False


@dataclass(frozen=True, slots=True)
class ItemData:
    name: str
    grams: float
    kcal: float
    protein: float
    fat: float
    carbs: float


def per_portion(recipe: Recipe) -> Macros:
    return recipe.totals().scaled(1 / max(1, recipe.portions))


def can_view(recipe: Recipe, user: User) -> bool:
    return recipe.status == Status.PUBLIC or recipe.owner_id == user.id or user.is_admin


async def get_visible(session: AsyncSession, user: User, recipe_id: int) -> Recipe:
    recipe = await session.get(Recipe, recipe_id)
    if recipe is None or not can_view(recipe, user):
        raise RecipeError("recipe_not_found")
    return recipe


async def get_own(session: AsyncSession, user: User, recipe_id: int) -> Recipe:
    recipe = await session.get(Recipe, recipe_id)
    if recipe is None or recipe.owner_id != user.id:
        raise RecipeError("recipe_not_found")
    return recipe


async def stats(session: AsyncSession, user: User, ids: list[int]) -> dict[int, Stats]:
    if not ids:
        return {}
    favs = dict(
        (
            await session.execute(
                select(RecipeFavorite.recipe_id, func.count())
                .where(RecipeFavorite.recipe_id.in_(ids))
                .group_by(RecipeFavorite.recipe_id)
            )
        ).all()
    )
    ratings = {
        rid: (avg, n)
        for rid, avg, n in await session.execute(
            select(RecipeRating.recipe_id, func.avg(RecipeRating.stars), func.count())
            .where(RecipeRating.recipe_id.in_(ids))
            .group_by(RecipeRating.recipe_id)
        )
    }
    cooked = dict(
        (
            await session.execute(
                select(Meal.recipe_id, func.count())
                .where(Meal.recipe_id.in_(ids))
                .group_by(Meal.recipe_id)
            )
        ).all()
    )
    mine_fav = set(
        await session.scalars(
            select(RecipeFavorite.recipe_id).where(
                RecipeFavorite.user_id == user.id, RecipeFavorite.recipe_id.in_(ids)
            )
        )
    )
    my_ratings = dict(
        (
            await session.execute(
                select(RecipeRating.recipe_id, RecipeRating.stars).where(
                    RecipeRating.user_id == user.id, RecipeRating.recipe_id.in_(ids)
                )
            )
        ).all()
    )
    cooked_by_me = set(
        await session.scalars(
            select(Meal.recipe_id)
            .where(Meal.user_id == user.id, Meal.recipe_id.in_(ids))
            .distinct()
        )
    )
    return {
        rid: Stats(
            favorites=favs.get(rid, 0),
            rating=float(ratings[rid][0]) if rid in ratings else None,
            ratings=ratings[rid][1] if rid in ratings else 0,
            cooked=cooked.get(rid, 0),
            is_favorite=rid in mine_fav,
            my_rating=my_ratings.get(rid),
            cooked_by_me=rid in cooked_by_me,
        )
        for rid in ids
    }


def _like(q: str) -> str:
    return "%" + re.sub(r"([%_\\])", r"\\\1", q.strip()) + "%"


async def search(
    session: AsyncSession,
    user: User,
    scope: Scope,
    q: str | None,
    filters: set[Filter],
    remaining_kcal: float | None,
    limit: int,
    offset: int,
) -> list[Recipe]:
    query: Select = select(Recipe)
    if scope == Scope.MINE:
        query = query.where(Recipe.owner_id == user.id)
    elif scope == Scope.FAVORITES:
        query = query.join(
            RecipeFavorite,
            and_(RecipeFavorite.recipe_id == Recipe.id, RecipeFavorite.user_id == user.id),
        ).where(or_(Recipe.status == Status.PUBLIC, Recipe.owner_id == user.id))
    else:
        query = query.where(Recipe.status == Status.PUBLIC)
    if q and q.strip():
        query = query.where(Recipe.title.ilike(_like(q), escape="\\"))
    if filters:
        totals = (
            select(
                RecipeItem.recipe_id.label("rid"),
                func.sum(RecipeItem.kcal).label("kcal"),
                func.sum(RecipeItem.protein).label("protein"),
            )
            .group_by(RecipeItem.recipe_id)
            .subquery()
        )
        query = query.join(totals, totals.c.rid == Recipe.id)
        portion_kcal = totals.c.kcal / Recipe.portions
        if Filter.PROTEIN in filters:
            query = query.where(totals.c.protein * 4 >= totals.c.kcal * PROTEIN_SHARE)
        if Filter.LIGHT in filters:
            query = query.where(portion_kcal <= LIGHT_KCAL)
        if Filter.FITS in filters and remaining_kcal is not None:
            query = query.where(portion_kcal <= max(0.0, remaining_kcal))
    order = Recipe.updated_at.desc() if scope == Scope.MINE else Recipe.published_at.desc()
    query = query.order_by(order.nulls_last(), Recipe.id.desc()).limit(limit).offset(offset)
    return list(await session.scalars(query))


# Protein matters most when choosing what to cook for the rest of the day.
GAP_WEIGHTS = {"protein": 2.0, "fat": 1.0, "carbs": 1.0}
# Grams of a macro still missing before it counts as a gap worth filling.
MIN_GAP_G = 5.0
# How far a portion may go past what's left before it stops being a suggestion.
KCAL_SLACK = 1.05
FAT_SLACK_G = 8.0


def covers(portion: Macros, remaining: Macros) -> dict[str, int]:
    """Percent of each missing macro the portion would cover, capped at 100."""
    result = {}
    for name in GAP_WEIGHTS:
        gap = getattr(remaining, name)
        if gap >= MIN_GAP_G:
            result[name] = round(min(1.0, getattr(portion, name) / gap) * 100)
    return result


def gap_score(portion: Macros, remaining: Macros) -> float | None:
    """How well a portion fills the day's macro gap; None when it doesn't fit what's left."""
    if portion.kcal <= 0 or portion.kcal > remaining.kcal * KCAL_SLACK:
        return None
    if portion.fat > max(0.0, remaining.fat) + FAT_SLACK_G:
        return None
    filled = weight = overshoot = 0.0
    for name, w in GAP_WEIGHTS.items():
        gap, value = getattr(remaining, name), getattr(portion, name)
        if gap >= MIN_GAP_G:
            filled += w * min(1.0, value / gap)
            weight += w
        overshoot += max(0.0, value - max(0.0, gap)) / max(gap, 20.0)
    if weight == 0:
        return None
    return filled / weight - 0.5 * overshoot


async def suggestions(
    session: AsyncSession, user: User, remaining: Macros
) -> list[tuple[Recipe, dict[str, int]]]:
    """Visible recipes that best fill what's left of today's macros, with how much they cover."""
    if remaining.kcal < 150:
        return []
    favorite = exists().where(
        RecipeFavorite.recipe_id == Recipe.id, RecipeFavorite.user_id == user.id
    )
    candidates = await session.scalars(
        select(Recipe).where(
            or_(Recipe.status == Status.PUBLIC, Recipe.owner_id == user.id, favorite)
        )
    )
    scored = []
    for recipe in candidates:
        portion = per_portion(recipe)
        score = gap_score(portion, remaining)
        if score is not None:
            scored.append((score, recipe.id, recipe, covers(portion, remaining)))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [(recipe, cover) for _, _, recipe, cover in scored[:SUGGESTIONS]]


def apply(
    recipe: Recipe,
    title: str,
    portions: int,
    cooked_grams: float | None,
    items: list[ItemData],
    steps: list[dict],
    photo_key: str | None,
) -> list[str]:
    """Overwrite the recipe's content; returns photo keys that are no longer used."""
    before = set(recipe.photo_keys())
    recipe.title = title
    recipe.portions = portions
    recipe.cooked_grams = cooked_grams
    recipe.items = [
        RecipeItem(
            position=n,
            name=item.name,
            grams=item.grams,
            kcal=item.kcal,
            protein=item.protein,
            fat=item.fat,
            carbs=item.carbs,
        )
        for n, item in enumerate(items)
    ]
    recipe.steps = steps
    recipe.photo_key = photo_key
    return sorted(before - set(recipe.photo_keys()))


def resubmit_after_edit(recipe: Recipe, owner: User) -> None:
    """An edited published recipe goes back through moderation unless an admin owns it."""
    if recipe.status in (Status.PUBLIC, Status.PENDING) and not owner.is_admin:
        recipe.status = Status.PENDING


def fork(recipe: Recipe, user: User) -> Recipe:
    """A private copy the user can change; photos stay with the original."""
    return Recipe(
        owner_id=user.id,
        forked_from_id=recipe.id,
        title=recipe.title,
        portions=recipe.portions,
        cooked_grams=recipe.cooked_grams,
        steps=[{"text": s["text"], "photo": None} for s in recipe.steps],
        status=Status.PRIVATE,
        items=[
            RecipeItem(
                position=i.position,
                name=i.name,
                grams=i.grams,
                kcal=i.kcal,
                protein=i.protein,
                fat=i.fat,
                carbs=i.carbs,
            )
            for i in recipe.items
        ],
    )


def to_meal(
    recipe: Recipe,
    user: User,
    day: date,
    item_grams: list[float],
    portions: float | None,
    grams: float | None,
    cooked_grams: float | None,
) -> Meal:
    """A diary snapshot of the eaten share, with this time's ingredient amounts."""
    if len(item_grams) != len(recipe.items) or not any(g > 0 for g in item_grams):
        raise RecipeError("invalid_items")
    raw = sum(item_grams)
    if portions is not None:
        share = portions / max(1, recipe.portions)
    elif grams is not None:
        cooked = cooked_grams or (
            recipe.cooked_grams * raw / recipe.raw_grams()
            if recipe.cooked_grams and recipe.raw_grams()
            else raw
        )
        share = grams / cooked
    else:
        raise RecipeError("invalid_amount")
    if not 0 < share <= 10:
        raise RecipeError("invalid_amount")
    items = []
    for item, g in zip(recipe.items, item_grams, strict=True):
        if g <= 0 or item.grams <= 0:
            continue
        k = g / item.grams * share
        items.append(
            MealItem(
                name=item.name,
                grams=g * share,
                kcal=item.kcal * k,
                protein=item.protein * k,
                fat=item.fat * k,
                carbs=item.carbs * k,
            )
        )
    return Meal(
        user_id=user.id,
        day=day,
        source="recipe",
        title=recipe.title,
        scale=1.0,
        recipe_id=recipe.id,
        items=items,
    )


def publish_problems(recipe: Recipe) -> list[str]:
    problems = []
    if not recipe.items:
        problems.append("no_items")
    if not recipe.photo_key:
        problems.append("no_photo")
    if not any(s.get("text", "").strip() for s in recipe.steps):
        problems.append("no_steps")
    return problems


def submit(recipe: Recipe, owner: User, author_name: str) -> None:
    problems = publish_problems(recipe)
    if problems:
        raise RecipeError(problems[0])
    recipe.author_name = author_name
    recipe.reject_reason = None
    if owner.is_admin:
        approve(recipe)
    else:
        recipe.status = Status.PENDING


def approve(recipe: Recipe) -> None:
    recipe.status = Status.PUBLIC
    recipe.reject_reason = None
    recipe.published_at = recipe.published_at or utcnow()


def reject(recipe: Recipe, reason: str) -> None:
    recipe.status = Status.REJECTED
    recipe.reject_reason = reason


def plausibility(recipe: Recipe) -> list[str]:
    """Warnings for the moderator about numbers that look off."""
    warnings = []
    for item in recipe.items:
        if item.grams <= 0:
            continue
        per100 = item.kcal / item.grams * 100
        macro_kcal = (item.protein * 4 + item.carbs * 4 + item.fat * 9) / item.grams * 100
        if per100 > 900:
            warnings.append(f"{item.name}: {per100:.0f} kcal/100 g")
        elif per100 > 50 and abs(macro_kcal - per100) > per100 * 0.35:
            warnings.append(f"{item.name}: macros give {macro_kcal:.0f}, kcal says {per100:.0f}")
        for name, value in (("protein", item.protein), ("fat", item.fat), ("carbs", item.carbs)):
            if value / item.grams > 1:
                warnings.append(f"{item.name}: {name} over 100 g per 100 g")
    if recipe.cooked_grams and recipe.raw_grams():
        ratio = recipe.cooked_grams / recipe.raw_grams()
        if not 0.3 <= ratio <= 3.5:
            warnings.append(f"cooked {recipe.cooked_grams:.0f} g vs raw {recipe.raw_grams():.0f} g")
    return warnings


async def can_rate(session: AsyncSession, user: User, recipe: Recipe) -> bool:
    if recipe.owner_id == user.id or recipe.status != Status.PUBLIC:
        return False
    return bool(
        await session.scalar(
            select(exists().where(Meal.user_id == user.id, Meal.recipe_id == recipe.id))
        )
    )
