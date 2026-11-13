"""Clarifying questions on voice meals: option buttons or a free-text reply."""

from contextlib import suppress
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Filter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot.texts import t
from belok.db.models import Meal, User
from belok.i18n import Language
from belok.llm.analyzer import AnalysisError, FoodAnalyzer
from belok.services.meals import answer_question
from belok.services.repo import get_meal
from belok.services.widgets import refresh_day_card, update_meal_widget

router = Router(name="clarify")

PREFIX = "cq"
SKIP = "x"


def _data(meal_id: int, widget_id: int, choice: int | str) -> str:
    return f"{PREFIX}:{meal_id}:{widget_id}:{choice}"


def _parse(data: str | None) -> tuple[int, int, str] | None:
    parts = (data or "").split(":")
    if len(parts) != 4 or parts[0] != PREFIX or not parts[1].isdigit() or not parts[2].isdigit():
        return None
    return int(parts[1]), int(parts[2]), parts[3]


def _question_ref(message: Message) -> tuple[int, int] | None:
    """Meal and widget ids of the question message, read from its buttons."""
    markup = message.reply_markup
    if markup is None or not markup.inline_keyboard:
        return None
    parsed = _parse(markup.inline_keyboard[0][0].callback_data)
    return (parsed[0], parsed[1]) if parsed else None


async def ask_question(message: Message, lang: Language, meal: Meal, widget_id: int) -> None:
    question = meal.question or {}
    rows = [
        [InlineKeyboardButton(text=option, callback_data=_data(meal.id, widget_id, i))]
        for i, option in enumerate(question.get("options", []))
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text=t(lang, "clarify_skip"), callback_data=_data(meal.id, widget_id, SKIP)
            )
        ]
    )
    await message.answer(
        t(lang, "clarify_ask", question=escape(question.get("text", ""))),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith(f"{PREFIX}:"))
async def answer_button(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    user: User,
    lang: Language,
    analyzer: FoodAnalyzer,
) -> None:
    parsed = _parse(callback.data)
    meal = await get_meal(session, user.id, parsed[0]) if parsed else None
    if parsed is None or meal is None or meal.question is None:
        await callback.answer(t(lang, "clarify_gone"))
        await _drop_buttons(callback.message)
        return
    _, widget_id, choice = parsed
    if choice == SKIP:
        meal.question = None
        await session.commit()
        await callback.answer()
        await _finish(callback.message, t(lang, "clarify_skipped"))
        return
    options = meal.question.get("options", [])
    if not choice.isdigit() or int(choice) >= len(options):
        await callback.answer(t(lang, "clarify_gone"))
        return
    await callback.answer(t(lang, "clarify_thinking"))
    await _apply(
        bot, session, user, lang, analyzer, meal, widget_id, options[int(choice)], callback.message
    )


class _RepliesToQuestion(Filter):
    async def __call__(self, message: Message, bot: Bot) -> bool | dict:
        replied = message.reply_to_message
        if replied is None or replied.from_user is None or replied.from_user.id != bot.id:
            return False
        ref = _question_ref(replied)
        return {"question_ref": ref} if ref else False


@router.message(F.text & ~F.text.startswith("/"), _RepliesToQuestion())
async def answer_text(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    user: User,
    lang: Language,
    analyzer: FoodAnalyzer,
    question_ref: tuple[int, int],
) -> None:
    meal_id, widget_id = question_ref
    meal = await get_meal(session, user.id, meal_id)
    if meal is None or meal.question is None:
        await message.answer(t(lang, "clarify_gone"))
        return
    answer = message.text.strip()[:200]
    await _apply(
        bot, session, user, lang, analyzer, meal, widget_id, answer, message.reply_to_message
    )


async def _apply(
    bot: Bot,
    session: AsyncSession,
    user: User,
    lang: Language,
    analyzer: FoodAnalyzer,
    meal: Meal,
    widget_id: int,
    answer: str,
    question_message: object,
) -> None:
    try:
        updated = await answer_question(
            session,
            None,
            user,
            meal,
            answer,
            lambda prev, q, a: analyzer.clarify(prev, q, a, lang),
        )
    except AnalysisError:
        await session.commit()
        await bot.send_message(user.id, t(lang, "voice_failed"))
        return
    await session.commit()
    if updated and widget_id:
        await update_meal_widget(bot, session, user, meal, widget_id)
    totals = meal.totals()
    text = t(
        lang,
        "clarify_done",
        answer=escape(answer),
        title=escape(meal.title),
        kcal=totals.kcal,
        p=totals.protein,
        f=totals.fat,
        c=totals.carbs,
    )
    await _finish(question_message, text)
    await refresh_day_card(bot, session, user)


async def _finish(message: object, text: str) -> None:
    if not isinstance(message, Message):
        return
    with suppress(TelegramAPIError):
        await message.edit_text(text, reply_markup=None)


async def _drop_buttons(message: object) -> None:
    if not isinstance(message, Message):
        return
    with suppress(TelegramAPIError):
        await message.edit_reply_markup(reply_markup=None)
