from aiogram import Bot
from aiogram.types import BotCommandScopeChat, MenuButtonWebApp, WebAppInfo

from belok.bot.texts import t
from belok.config import Settings
from belok.i18n import Language


def menu_button(lang: Language, settings: Settings) -> MenuButtonWebApp:
    return MenuButtonWebApp(text=t(lang, "open_app"), web_app=WebAppInfo(url=settings.webapp_url))


async def setup_defaults(bot: Bot, settings: Settings) -> None:
    await bot.delete_my_commands()
    await bot.delete_my_commands(language_code="ru")
    if settings.webapp_url:
        await bot.set_chat_menu_button(menu_button=menu_button(Language.EN, settings))


async def reset_chat_menu(bot: Bot, chat_id: int, lang: Language, settings: Settings) -> None:
    """Drops command lists set per chat by older versions and shows the app button instead."""
    await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=chat_id))
    if settings.webapp_url:
        await bot.set_chat_menu_button(chat_id=chat_id, menu_button=menu_button(lang, settings))
