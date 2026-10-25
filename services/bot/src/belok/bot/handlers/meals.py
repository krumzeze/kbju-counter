import logging
from collections.abc import Awaitable, Callable

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot import texts
from belok.bot.keyboards import MealCb, meal_kb
from belok.config import Settings
from belok.db.models import LlmUsage, Meal, MealItem, User
from belok.llm.analyzer import AnalysisError, AnalysisResult, FoodAnalyzer
from belok.services.repo import analyses_on, get_meal
from belok.timeutil import local_today

log = logging.getLogger(__name__)
router = Router(name="meals")

SCALE_STEP = 0.25
MIN_SCALE, MAX_SCALE = 0.25, 5.0


@router.message(F.photo)
async def on_photo(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    user: User,
    analyzer: FoodAnalyzer,
    settings: Settings,
) -> None:
    if not await _within_limit(message, session, user, settings):
        return
    status = await message.answer("Смотрю на фото…")
    image = await bot.download(message.photo[-1])
    await _analyze(
        status, session, user, "photo", lambda: analyzer.from_photo(image.read(), message.caption)
    )


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def on_text_meal(
    message: Message,
    session: AsyncSession,
    user: User,
    analyzer: FoodAnalyzer,
    settings: Settings,
) -> None:
    if len(message.text) > 500:
        await message.answer("Слишком длинное описание, опиши блюдо короче")
        return
    if not await _within_limit(message, session, user, settings):
        return
    status = await message.answer("Считаю…")
    await _analyze(status, session, user, "text", lambda: analyzer.from_text(message.text))


@router.callback_query(MealCb.filter())
async def on_meal_action(
    callback: CallbackQuery, callback_data: MealCb, session: AsyncSession, user: User
) -> None:
    meal = await get_meal(session, user.id, callback_data.id)
    if meal is None:
        await callback.answer("Запись не найдена")
        return

    if callback_data.action == "del":
        await session.delete(meal)
        await callback.message.edit_text(f"<s>{texts.meal_card(meal)}</s>\n\nУдалено")
        await callback.answer()
        return

    step = SCALE_STEP if callback_data.action == "inc" else -SCALE_STEP
    new_scale = min(MAX_SCALE, max(MIN_SCALE, meal.scale + step))
    if new_scale == meal.scale:
        await callback.answer()
        return
    meal.scale = new_scale
    await callback.message.edit_text(texts.meal_card(meal), reply_markup=meal_kb(meal.id))
    await callback.answer()


async def _within_limit(
    message: Message, session: AsyncSession, user: User, settings: Settings
) -> bool:
    used = await analyses_on(session, user.id, local_today(user.timezone))
    if used >= settings.daily_analysis_limit:
        await message.answer("На сегодня лимит распознаваний исчерпан, приходи завтра")
        return False
    return True


async def _analyze(
    status: Message,
    session: AsyncSession,
    user: User,
    kind: str,
    call: Callable[[], Awaitable[AnalysisResult]],
) -> None:
    today = local_today(user.timezone)
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
        await status.edit_text("Не получилось посчитать, попробуй ещё раз чуть позже")
        return

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
        )
    )
    analysis = result.analysis
    if not analysis.items:
        await status.edit_text("Не вижу здесь еды. Попробуй другое фото или опиши текстом")
        return

    meal = Meal(
        user_id=user.id,
        day=today,
        source=kind,
        title=analysis.title,
        scale=1.0,
        items=[MealItem(**item.model_dump()) for item in analysis.items],
    )
    session.add(meal)
    await session.flush()
    await status.edit_text(texts.meal_card(meal), reply_markup=meal_kb(meal.id))
