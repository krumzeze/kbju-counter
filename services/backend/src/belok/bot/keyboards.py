from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from belok.domain.nutrition import Goal, Sex


class SexCb(CallbackData, prefix="sex"):
    value: Sex


class GoalCb(CallbackData, prefix="goal"):
    value: Goal


class MealCb(CallbackData, prefix="meal"):
    id: int
    action: str


def sex_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Мужской", callback_data=SexCb(value=Sex.MALE))
    kb.button(text="Женский", callback_data=SexCb(value=Sex.FEMALE))
    return kb.as_markup()


def goal_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Похудеть", callback_data=GoalCb(value=Goal.LOSE))
    kb.button(text="Держать вес", callback_data=GoalCb(value=Goal.MAINTAIN))
    kb.button(text="Набрать массу", callback_data=GoalCb(value=Goal.GAIN))
    kb.adjust(1)
    return kb.as_markup()


def meal_kb(meal_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Порция −25%", callback_data=MealCb(id=meal_id, action="dec"))
    kb.button(text="Порция +25%", callback_data=MealCb(id=meal_id, action="inc"))
    kb.button(text="Удалить", callback_data=MealCb(id=meal_id, action="del"))
    kb.adjust(2, 1)
    return kb.as_markup()
