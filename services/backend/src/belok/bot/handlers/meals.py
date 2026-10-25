from collections.abc import Awaitable, Callable

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot import texts
from belok.bot.keyboards import MealCb, meal_kb
from belok.config import Settings
from belok.db.models import User
from belok.llm.analyzer import AnalysisError, AnalysisResult, FoodAnalyzer
from belok.services.meals import (
    SCALE_STEP,
    DailyLimitReached,
    analyze_meal,
    clamp_scale,
    ensure_within_limit,
)
from belok.services.repo import get_meal

router = Router(name="meals")


@router.message(F.photo)
async def on_photo(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    user: User,
    analyzer: FoodAnalyzer,
    settings: Settings,
) -> None:
    async def call() -> AnalysisResult:
        image = await bot.download(message.photo[-1])
        return await analyzer.from_photo(image.read(), message.caption)

    await _analyze(message, session, user, settings, "photo", "Смотрю на фото…", call)


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
    await _analyze(
        message,
        session,
        user,
        settings,
        "text",
        "Считаю…",
        lambda: analyzer.from_text(message.text),
    )


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
    new_scale = clamp_scale(meal.scale + step)
    if new_scale == meal.scale:
        await callback.answer()
        return
    meal.scale = new_scale
    await callback.message.edit_text(texts.meal_card(meal), reply_markup=meal_kb(meal.id))
    await callback.answer()


async def _analyze(
    message: Message,
    session: AsyncSession,
    user: User,
    settings: Settings,
    kind: str,
    progress_text: str,
    call: Callable[[], Awaitable[AnalysisResult]],
) -> None:
    try:
        await ensure_within_limit(session, user, settings.daily_analysis_limit)
    except DailyLimitReached:
        await message.answer("На сегодня лимит распознаваний исчерпан, приходи завтра")
        return

    status = await message.answer(progress_text)
    try:
        meal = await analyze_meal(session, user, kind, call)
    except AnalysisError:
        await status.edit_text("Не получилось посчитать, попробуй ещё раз чуть позже")
        return
    if meal is None:
        await status.edit_text("Не вижу здесь еды. Попробуй другое фото или опиши текстом")
        return
    await status.edit_text(texts.meal_card(meal), reply_markup=meal_kb(meal.id))
