from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from belok.bot.texts import t
from belok.domain.nutrition import Goal, Sex
from belok.i18n import Language


class LanguageCb(CallbackData, prefix="lang"):
    value: Language


class SexCb(CallbackData, prefix="sex"):
    value: Sex


class GoalCb(CallbackData, prefix="goal"):
    value: Goal


class MealCb(CallbackData, prefix="meal"):
    id: int
    action: str


def language_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🇷🇺 Русский", callback_data=LanguageCb(value=Language.RU))
    kb.button(text="🇬🇧 English", callback_data=LanguageCb(value=Language.EN))
    return kb.as_markup()


def sex_kb(lang: Language) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "male"), callback_data=SexCb(value=Sex.MALE))
    kb.button(text=t(lang, "female"), callback_data=SexCb(value=Sex.FEMALE))
    return kb.as_markup()


def goal_kb(lang: Language) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "goal_lose"), callback_data=GoalCb(value=Goal.LOSE))
    kb.button(text=t(lang, "goal_maintain"), callback_data=GoalCb(value=Goal.MAINTAIN))
    kb.button(text=t(lang, "goal_gain"), callback_data=GoalCb(value=Goal.GAIN))
    kb.adjust(1)
    return kb.as_markup()


def meal_kb(lang: Language, meal_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "portion_dec"), callback_data=MealCb(id=meal_id, action="dec"))
    kb.button(text=t(lang, "portion_inc"), callback_data=MealCb(id=meal_id, action="inc"))
    kb.button(text=t(lang, "delete"), callback_data=MealCb(id=meal_id, action="del"))
    kb.adjust(2, 1)
    return kb.as_markup()
