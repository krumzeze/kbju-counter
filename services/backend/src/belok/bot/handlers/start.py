from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot import texts
from belok.bot.keyboards import GoalCb, LanguageCb, SexCb, goal_kb, language_kb, sex_kb
from belok.bot.menu import apply_language
from belok.bot.texts import t
from belok.config import Settings
from belok.db.models import User
from belok.domain.nutrition import daily_target
from belok.i18n import Language
from belok.services.promos import PROMO_PREFIX, PromoResult, redeem
from belok.services.referrals import referral_stats
from belok.services.users import REFERRAL_PREFIX, update_profile

router = Router(name="start")


class Onboarding(StatesGroup):
    sex = State()
    age = State()
    height = State()
    weight = State()
    goal = State()


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    lang: Language,
) -> None:
    if command.args and command.args.startswith(PROMO_PREFIX):
        await _apply_promo(message, session, user, lang, command.args.removeprefix(PROMO_PREFIX))
    if user.language is None:
        await message.answer(t(lang, "choose_language"), reply_markup=language_kb())
        return
    if user.profile_complete:
        await message.answer(t(lang, "help"))
        return
    await _begin(message, state, lang)


@router.message(Command("language"))
async def cmd_language(message: Message, lang: Language) -> None:
    await message.answer(t(lang, "choose_language"), reply_markup=language_kb())


@router.callback_query(LanguageCb.filter())
async def on_language(
    callback: CallbackQuery,
    callback_data: LanguageCb,
    state: FSMContext,
    bot: Bot,
    user: User,
    settings: Settings,
) -> None:
    lang = user.language = callback_data.value
    await apply_language(bot, callback.message.chat.id, lang, settings)
    await callback.message.edit_text(t(lang, "language_set"))
    await callback.answer()
    if user.profile_complete:
        await callback.message.answer(t(lang, "help"))
    else:
        await _begin(callback.message, state, lang)


@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext, lang: Language) -> None:
    await _begin(message, state, lang)


@router.message(Command("promo"))
async def cmd_promo(
    message: Message, command: CommandObject, session: AsyncSession, user: User, lang: Language
) -> None:
    if not command.args:
        await message.answer(t(lang, "promo_usage"))
        return
    await _apply_promo(message, session, user, lang, command.args)


@router.message(Command("invite"))
async def cmd_invite(
    message: Message, session: AsyncSession, user: User, settings: Settings, lang: Language
) -> None:
    if not settings.bot_username:
        await message.answer(t(lang, "invites_unavailable"))
        return
    invited, paid, days = await referral_stats(session, user.id)
    link = f"https://t.me/{settings.bot_username}?start={REFERRAL_PREFIX}{user.referral_code}"
    await message.answer(texts.invite(lang, link, settings, invited, paid, days))


async def _apply_promo(
    message: Message, session: AsyncSession, user: User, lang: Language, code: str
) -> None:
    result, days = await redeem(session, user, code)
    if result == PromoResult.OK:
        await message.answer(texts.promo_ok(lang, days))
    else:
        await message.answer(t(lang, result))


@router.message(Command("help"))
async def cmd_help(message: Message, lang: Language) -> None:
    await message.answer(t(lang, "help"))


async def _begin(message: Message, state: FSMContext, lang: Language) -> None:
    await state.set_state(Onboarding.sex)
    await message.answer(t(lang, "welcome"), reply_markup=sex_kb(lang))


@router.callback_query(Onboarding.sex, SexCb.filter())
async def on_sex(
    callback: CallbackQuery, callback_data: SexCb, state: FSMContext, lang: Language
) -> None:
    await state.update_data(sex=callback_data.value)
    await state.set_state(Onboarding.age)
    await callback.message.edit_text(t(lang, "ask_age"))
    await callback.answer()


@router.message(Onboarding.age, F.text)
async def on_age(message: Message, state: FSMContext, lang: Language) -> None:
    age = _parse_number(message.text, 12, 100)
    if age is None:
        await message.answer(t(lang, "bad_age"))
        return
    await state.update_data(age=int(age))
    await state.set_state(Onboarding.height)
    await message.answer(t(lang, "ask_height"))


@router.message(Onboarding.height, F.text)
async def on_height(message: Message, state: FSMContext, lang: Language) -> None:
    height = _parse_number(message.text, 120, 230)
    if height is None:
        await message.answer(t(lang, "bad_height"))
        return
    await state.update_data(height=int(height))
    await state.set_state(Onboarding.weight)
    await message.answer(t(lang, "ask_weight"))


@router.message(Onboarding.weight, F.text)
async def on_weight(message: Message, state: FSMContext, lang: Language) -> None:
    weight = _parse_number(message.text, 30, 300)
    if weight is None:
        await message.answer(t(lang, "bad_weight"))
        return
    await state.update_data(weight=weight)
    await state.set_state(Onboarding.goal)
    await message.answer(t(lang, "ask_goal"), reply_markup=goal_kb(lang))


@router.callback_query(Onboarding.goal, GoalCb.filter())
async def on_goal(
    callback: CallbackQuery,
    callback_data: GoalCb,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    lang: Language,
) -> None:
    data = await state.get_data()
    await state.clear()

    await update_profile(
        session, user, data["sex"], data["age"], data["height"], data["weight"], callback_data.value
    )

    target = daily_target(user.sex, data["weight"], user.height_cm, data["age"], user.goal)
    done = t(lang, "onboarding_done", target=texts.macros_line(lang, target))
    await callback.message.edit_text(f"{done}\n\n{t(lang, 'help')}")
    await callback.answer()


def _parse_number(text: str, low: float, high: float) -> float | None:
    try:
        value = float(text.replace(",", ".").strip())
    except ValueError:
        return None
    return value if low <= value <= high else None
