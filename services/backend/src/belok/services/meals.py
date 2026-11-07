import logging
from collections.abc import Awaitable, Callable
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from belok.config import Settings
from belok.db.models import LlmUsage, Meal, MealItem, User
from belok.llm.analyzer import AnalysisError, AnalysisResult, FoodAnalysis, FoodItem
from belok.services.access import has_access
from belok.services.repo import analyses_on
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


def clamp_scale(scale: float) -> float:
    return min(MAX_SCALE, max(MIN_SCALE, scale))
