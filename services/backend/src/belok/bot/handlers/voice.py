from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot.texts import t
from belok.config import Settings
from belok.db.models import Meal, User
from belok.i18n import Language
from belok.llm.analyzer import AnalysisError, FoodAnalyzer
from belok.llm.speech import SpeechError, SpeechToText
from belok.services.access import has_access
from belok.services.meals import DailyLimitReached, analyze_meal, ensure_within_limit
from belok.services.repo import day_summary
from belok.timeutil import local_today, utcnow

router = Router(name="voice")

MAX_VOICE_SECONDS = 90


@router.message(F.voice)
async def voice_meal(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    user: User,
    settings: Settings,
    lang: Language,
    analyzer: FoodAnalyzer,
    stt: SpeechToText | None,
) -> None:
    markup = _app_button(settings, lang)
    if not user.profile_complete:
        await message.answer(t(lang, "voice_need_profile"), reply_markup=markup)
        return
    if not has_access(user, utcnow()):
        await message.answer(t(lang, "voice_no_access"), reply_markup=markup)
        return
    if stt is None:
        await message.answer(t(lang, "voice_unavailable"), reply_markup=markup)
        return
    if message.voice.duration > MAX_VOICE_SECONDS:
        await message.answer(t(lang, "voice_too_long", seconds=MAX_VOICE_SECONDS))
        return
    try:
        await ensure_within_limit(session, user, settings.daily_analysis_limit)
    except DailyLimitReached:
        await message.answer(t(lang, "daily_limit"))
        return

    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    audio = await bot.download(message.voice)
    try:
        text = await stt.transcribe(audio.read(), lang)
    except SpeechError:
        await message.answer(t(lang, "voice_failed"))
        return
    if not text:
        await message.answer(t(lang, "voice_empty"))
        return

    try:
        meal = await analyze_meal(session, user, "voice", lambda: analyzer.from_text(text, lang))
    except AnalysisError:
        await message.answer(t(lang, "voice_failed"))
        return
    if meal is None:
        await message.answer(t(lang, "voice_no_food", text=escape(text)))
        return
    user.last_seen_at = utcnow()
    await session.commit()
    summary = await day_summary(session, user, local_today(user.timezone))
    target = summary.target.macros.kcal if summary.target else None
    await message.answer(
        meal_text(lang, text, meal, summary.eaten.kcal, target), reply_markup=markup
    )


def meal_text(
    lang: Language, heard: str, meal: Meal, eaten_kcal: float, target_kcal: float | None
) -> str:
    totals = meal.totals()
    unit = "г" if lang == Language.RU else "g"
    kcal = "ккал" if lang == Language.RU else "kcal"
    lines = [f"🎙 <i>«{escape(heard)}»</i>", "", f"<b>{escape(meal.title)}</b>"]
    for item in meal.items:
        lines.append(f"• {escape(item.name)}, {item.grams:.0f} {unit}: {item.kcal:.0f} {kcal}")
    lines += [
        "",
        t(lang, "voice_totals", kcal=totals.kcal, p=totals.protein, f=totals.fat, c=totals.carbs),
    ]
    if target_kcal:
        lines.append(t(lang, "voice_day", eaten=eaten_kcal, target=target_kcal))
    lines += ["", t(lang, "voice_edit_hint")]
    return "\n".join(lines)


def _app_button(settings: Settings, lang: Language) -> InlineKeyboardMarkup | None:
    if not settings.webapp_url:
        return None
    button = InlineKeyboardButton(
        text=t(lang, "open_app"), web_app=WebAppInfo(url=settings.webapp_url)
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])
