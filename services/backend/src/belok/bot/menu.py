from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, MenuButtonWebApp, WebAppInfo

from belok.bot.texts import COMMANDS, t
from belok.config import Settings
from belok.i18n import Language


def commands(lang: Language) -> list[BotCommand]:
    return [BotCommand(command=name, description=desc[lang]) for name, desc in COMMANDS.items()]


def menu_button(lang: Language, settings: Settings) -> MenuButtonWebApp:
    return MenuButtonWebApp(text=t(lang, "open_app"), web_app=WebAppInfo(url=settings.webapp_url))


async def setup_defaults(bot: Bot, settings: Settings) -> None:
    await bot.set_my_commands(commands(Language.EN))
    await bot.set_my_commands(commands(Language.RU), language_code="ru")
    if settings.webapp_url:
        await bot.set_chat_menu_button(menu_button=menu_button(Language.EN, settings))


async def apply_language(bot: Bot, chat_id: int, lang: Language, settings: Settings) -> None:
    await bot.set_my_commands(commands(lang), scope=BotCommandScopeChat(chat_id=chat_id))
    if settings.webapp_url:
        await bot.set_chat_menu_button(chat_id=chat_id, menu_button=menu_button(lang, settings))
