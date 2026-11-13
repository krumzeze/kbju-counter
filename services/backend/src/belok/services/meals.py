import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import date, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from belok.config import Settings
from belok.db.models import LlmUsage, Meal, MealItem, PhotoEval, User
from belok.images import BadImage
from belok.llm.analyzer import AnalysisError, AnalysisResult, FoodAnalysis, FoodItem
from belok.services.access import has_access
from belok.services.photos import PhotoStore, StorageError, eval_key, make_thumbnail, meal_key
from belok.services.repo import CLARIFY_KIND, analyses_on
from belok.timeutil import local_today, utcnow

log = logging.getLogger(__name__)

SCALE_STEP = 0.25
MIN_SCALE, MAX_SCALE = 0.25, 5.0


class DailyLimitReached(Exception):
    def __init__(self, premium: bool) -> None:
        super().__init__("premium" if premium else "free")
        self.premium = premium


def analysis_limit(user: User, settings: Settings) -> int:
    if user.daily_limit is not None:
        return user.daily_limit
    if has_access(user, utcnow()):
        return settings.daily_analysis_limit
    return settings.free_daily_analyses


async def analyses_left(session: AsyncSession, user: User, settings: Settings) -> int:
    used = await analyses_on(session, user.id, local_today(user.timezone))
    return max(0, analysis_limit(user, settings) - used)


async def ensure_within_limit(session: AsyncSession, user: User, settings: Settings) -> None:
    if await analyses_left(session, user, settings) == 0:
        raise DailyLimitReached(has_access(user, utcnow()))


async def run_analysis(
    session: AsyncSession,
    user: User,
    kind: str,
    call: Callable[[], Awaitable[AnalysisResult]],
) -> FoodAnalysis:
    """Run the analyzer and log usage."""
    today = local_today(user.timezone)
    # Return the DB connection to the pool while waiting on the LLM, which takes seconds.
    await session.commit()
    try:
        result = await call()
    except AnalysisError as exc:
        log.warning("analysis failed for user %s", user.id, exc_info=exc)
        session.add(
            LlmUsage(
                user_id=user.id,
                day=today,
                kind=kind,
                model=exc.model,
                latency_ms=exc.latency_ms,
                ok=False,
            )
        )
        raise

    session.add(
        LlmUsage(
            user_id=user.id,
            day=today,
            kind=kind,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cost_usd=result.cost_usd,
            latency_ms=result.latency_ms,
            ok=True,
            no_food=not result.analysis.items,
        )
    )
    return result.analysis


async def analyze_meal(
    session: AsyncSession,
    user: User,
    kind: str,
    call: Callable[[], Awaitable[AnalysisResult]],
) -> Meal | None:
    """Analyze and store a new meal. Returns None when no food was found."""
    analysis = await run_analysis(session, user, kind, call)
    if not analysis.items:
        return None
    meal = Meal(
        user_id=user.id,
        day=local_today(user.timezone),
        source=kind,
        title=analysis.title,
        scale=1.0,
        items=[MealItem(**item.model_dump()) for item in analysis.items],
    )
    question = analysis.usable_question()
    if question is not None:
        meal.question = question.model_dump()
    session.add(meal)
    await session.flush()
    return meal


def meal_analysis(meal: Meal) -> FoodAnalysis:
    """The meal as the analyzer sees it, with the portion scale applied."""
    return FoodAnalysis(
        title=meal.title,
        items=[
            FoodItem(
                name=i.name,
                grams=i.grams * meal.scale,
                kcal=i.kcal * meal.scale,
                protein=i.protein * meal.scale,
                fat=i.fat * meal.scale,
                carbs=i.carbs * meal.scale,
            )
            for i in meal.items
        ],
    )


def replace_items(meal: Meal, analysis: FoodAnalysis) -> None:
    meal.title = analysis.title
    meal.scale = 1.0
    meal.items = [MealItem(**item.model_dump()) for item in analysis.items]
    meal.question = None


async def answer_question(
    session: AsyncSession,
    store: PhotoStore | None,
    user: User,
    meal: Meal,
    answer: str,
    clarify: Callable[[FoodAnalysis, str, str], Awaitable[AnalysisResult]],
) -> bool:
    """Re-estimate the meal with the answer to its open question; False when no food came back.

    Answers are free: they don't count toward the daily limit, and each meal has one question.
    """
    question = meal.question["text"]
    previous = meal_analysis(meal)
    analysis = await run_analysis(
        session, user, CLARIFY_KIND, lambda: clarify(previous, question, answer)
    )
    if not analysis.items:
        meal.question = None
        return False
    await keep_for_eval(session, store, user, meal)
    replace_items(meal, analysis)
    return True


def manual_meal(
    user: User, day: date, title: str, grams: float, per_100g: tuple[float, float, float, float]
) -> Meal:
    kcal, protein, fat, carbs = (v * grams / 100 for v in per_100g)
    item = MealItem(name=title, grams=grams, kcal=kcal, protein=protein, fat=fat, carbs=carbs)
    return Meal(user_id=user.id, day=day, source="manual", title=title, scale=1.0, items=[item])


def copy_meal(meal: Meal, day: date) -> Meal:
    return Meal(
        user_id=meal.user_id,
        day=day,
        source=meal.source,
        title=meal.title,
        scale=meal.scale,
        items=[
            MealItem(
                name=i.name, grams=i.grams, kcal=i.kcal, protein=i.protein, fat=i.fat, carbs=i.carbs
            )
            for i in meal.items
        ],
    )


async def meal_history(
    session: AsyncSession, user_id: int, frequent: bool, limit: int
) -> list[tuple[Meal, int]]:
    """Past meals grouped by title: the latest copy of each and how many times it was eaten."""
    times = func.count().label("times")
    last = func.max(Meal.created_at).label("last")
    query = (
        select(func.max(Meal.id), times)
        .where(Meal.user_id == user_id)
        .group_by(func.lower(Meal.title))
        .order_by(*((times.desc(), last.desc()) if frequent else (last.desc(),)))
        .limit(limit)
    )
    rows = (await session.execute(query)).all()
    meals = {
        m.id: m
        for m in await session.scalars(select(Meal).where(Meal.id.in_([r[0] for r in rows])))
    }
    return [(meals[meal_id], n) for meal_id, n in rows]


def resize_item(meal: Meal, item: MealItem, grams: float) -> None:
    """Set the portion-adjusted weight of an item, scaling its macros to match."""
    base = grams / meal.scale
    ratio = base / item.grams
    item.grams = base
    item.kcal *= ratio
    item.protein *= ratio
    item.fat *= ratio
    item.carbs *= ratio


async def attach_photo(store: PhotoStore, meal: Meal, image: bytes) -> None:
    """Keep a thumbnail of the photo; the meal is saved either way."""
    try:
        thumb = await asyncio.to_thread(make_thumbnail, image)
        key = meal_key(meal.user_id)
        await store.put(key, thumb)
    except (BadImage, *StorageError):
        log.warning("failed to store photo for meal %s", meal.id, exc_info=True)
        return
    meal.photo_key = key


def photo_url(store: PhotoStore | None, meal: Meal, retention_days: int) -> str | None:
    if store is None or meal.photo_key is None:
        return None
    if utcnow() - meal.created_at > timedelta(days=retention_days):
        return None
    return store.url(meal.photo_key)


async def keep_for_eval(
    session: AsyncSession, store: PhotoStore | None, user: User, meal: Meal
) -> None:
    """Before the first correction of a photo meal, save the photo and the original analysis."""
    if store is None or meal.photo_key is None or not user.photo_eval_consent:
        return
    if await session.get(PhotoEval, meal.id) is not None:
        return
    key = eval_key(user.id, meal.id)
    try:
        await store.copy(meal.photo_key, key)
    except StorageError:
        log.warning("failed to keep photo of meal %s for eval", meal.id, exc_info=True)
        return
    original = meal_analysis(meal).model_dump()
    session.add(PhotoEval(meal_id=meal.id, user_id=user.id, photo_key=key, original=original))


async def meal_photo_keys(session: AsyncSession, meal: Meal) -> list[str]:
    keys = [meal.photo_key] if meal.photo_key else []
    sample = await session.get(PhotoEval, meal.id)
    if sample is not None:
        keys.append(sample.photo_key)
    return keys


async def drop_eval_photos(session: AsyncSession, store: PhotoStore | None, user: User) -> None:
    if store is not None:
        await store.delete_prefix(f"eval/{user.id}/")
    await session.execute(delete(PhotoEval).where(PhotoEval.user_id == user.id))


def clamp_scale(scale: float) -> float:
    return min(MAX_SCALE, max(MIN_SCALE, scale))
