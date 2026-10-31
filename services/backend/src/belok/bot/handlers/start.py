from aiogram import Bot, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot import texts
from belok.bot.menu import reset_chat_menu
from belok.bot.texts import t
from belok.config import Settings
from belok.db.models import User
from belok.i18n import Language
from belok.services.promos import PROMO_PREFIX, PromoResult, redeem

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    bot: Bot,
    session: AsyncSession,
    user: User,
    settings: Settings,
    lang: Language,
) -> None:
    if command.args and command.args.startswith(PROMO_PREFIX):
        code = command.args.removeprefix(PROMO_PREFIX)
        result, days = await redeem(session, user, code)
        await message.answer(
            texts.promo_ok(lang, days) if result == PromoResult.OK else t(lang, result)
        )
    await _open_app(message, bot, settings, lang)


@router.message()
async def any_message(message: Message, bot: Bot, settings: Settings, lang: Language) -> None:
    await _open_app(message, bot, settings, lang)


@router.callback_query()
async def stale_button(callback: CallbackQuery) -> None:
    await callback.answer()


async def _open_app(message: Message, bot: Bot, settings: Settings, lang: Language) -> None:
    await reset_chat_menu(bot, message.chat.id, lang, settings)
    if not settings.webapp_url:
        await message.answer(t(lang, "app_unavailable"))
        return
    button = InlineKeyboardButton(
        text=t(lang, "open_app"), web_app=WebAppInfo(url=settings.webapp_url)
    )
    await message.answer(
        t(lang, "welcome"), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]])
    )
