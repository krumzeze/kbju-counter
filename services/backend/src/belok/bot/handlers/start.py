from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot import texts
from belok.bot.keyboards import GoalCb, SexCb, goal_kb, sex_kb
from belok.db.models import User
from belok.domain.nutrition import daily_target
from belok.services.users import update_profile

router = Router(name="start")


class Onboarding(StatesGroup):
    sex = State()
    age = State()
    height = State()
    weight = State()
    goal = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, user: User) -> None:
    if user.profile_complete:
        await message.answer(texts.HELP)
        return
    await _begin(message, state)


@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext) -> None:
    await _begin(message, state)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP)


async def _begin(message: Message, state: FSMContext) -> None:
    await state.set_state(Onboarding.sex)
    await message.answer(
        "Привет! Я Белок: считаю калории по фото, слежу за тренировками и весом.\n\n"
        "Чтобы рассчитать твою норму, ответь на пять вопросов. Твой пол?",
        reply_markup=sex_kb(),
    )


@router.callback_query(Onboarding.sex, SexCb.filter())
async def on_sex(callback: CallbackQuery, callback_data: SexCb, state: FSMContext) -> None:
    await state.update_data(sex=callback_data.value)
    await state.set_state(Onboarding.age)
    await callback.message.edit_text("Сколько тебе лет?")
    await callback.answer()


@router.message(Onboarding.age, F.text)
async def on_age(message: Message, state: FSMContext) -> None:
    age = _parse_number(message.text, 12, 100)
    if age is None:
        await message.answer("Введи возраст числом, например 25")
        return
    await state.update_data(age=int(age))
    await state.set_state(Onboarding.height)
    await message.answer("Рост в сантиметрах?")


@router.message(Onboarding.height, F.text)
async def on_height(message: Message, state: FSMContext) -> None:
    height = _parse_number(message.text, 120, 230)
    if height is None:
        await message.answer("Введи рост в сантиметрах, например 178")
        return
    await state.update_data(height=int(height))
    await state.set_state(Onboarding.weight)
    await message.answer("Текущий вес в килограммах?")


@router.message(Onboarding.weight, F.text)
async def on_weight(message: Message, state: FSMContext) -> None:
    weight = _parse_number(message.text, 30, 300)
    if weight is None:
        await message.answer("Введи вес в килограммах, например 74.5")
        return
    await state.update_data(weight=weight)
    await state.set_state(Onboarding.goal)
    await message.answer("Какая цель?", reply_markup=goal_kb())


@router.callback_query(Onboarding.goal, GoalCb.filter())
async def on_goal(
    callback: CallbackQuery,
    callback_data: GoalCb,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    data = await state.get_data()
    await state.clear()

    await update_profile(
        session, user, data["sex"], data["age"], data["height"], data["weight"], callback_data.value
    )

    target = daily_target(user.sex, data["weight"], user.height_cm, data["age"], user.goal)
    await callback.message.edit_text(
        f"Готово! Твоя базовая норма в день без учёта активности:\n"
        f"<b>{texts.macros_line(target)}</b>\n\n"
        f"Шаги и тренировки будут добавлять к ней калории.\n\n{texts.HELP}"
    )
    await callback.answer()


def _parse_number(text: str, low: float, high: float) -> float | None:
    try:
        value = float(text.replace(",", ".").strip())
    except ValueError:
        return None
    return value if low <= value <= high else None
