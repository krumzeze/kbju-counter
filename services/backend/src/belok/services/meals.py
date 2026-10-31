import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import LlmUsage, Meal, MealItem, User
from belok.llm.analyzer import AnalysisError, AnalysisResult
from belok.services.repo import analyses_on
from belok.timeutil import local_today

log = logging.getLogger(__name__)

SCALE_STEP = 0.25
MIN_SCALE, MAX_SCALE = 0.25, 5.0


class DailyLimitReached(Exception):
    pass


async def ensure_within_limit(session: AsyncSession, user: User, default_limit: int) -> None:
    limit = user.daily_limit if user.daily_limit is not None else default_limit
    if await analyses_on(session, user.id, local_today(user.timezone)) >= limit:
        raise DailyLimitReached


async def analyze_meal(
    session: AsyncSession,
    user: User,
    kind: str,
    call: Callable[[], Awaitable[AnalysisResult]],
) -> Meal | None:
    """Run the analyzer, log usage and store the meal. Returns None when no food was found."""
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
    if not result.analysis.items:
        return None

    meal = Meal(
        user_id=user.id,
        day=today,
        source=kind,
        title=result.analysis.title,
        scale=1.0,
        items=[MealItem(**item.model_dump()) for item in result.analysis.items],
    )
    session.add(meal)
    await session.flush()
    return meal


def clamp_scale(scale: float) -> float:
    return min(MAX_SCALE, max(MIN_SCALE, scale))
