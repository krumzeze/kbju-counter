import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand, BotCommandScopeChat, MenuButtonWebApp, WebAppInfo

from belok.bot.texts import days_count, t
from belok.config import Settings
from belok.i18n import RUSSIAN_SPEAKING, Language

log = logging.getLogger(__name__)


def menu_button(lang: Language, settings: Settings) -> MenuButtonWebApp:
    return MenuButtonWebApp(text=t(lang, "open_app"), web_app=WebAppInfo(url=settings.webapp_url))


async def sync_profile(
    bot: Bot, lang: Language, language_code: str | None, trial_days: int
) -> None:
    """Sets name and descriptions only when they differ, setMyName has a tight rate limit."""
    name = t(lang, "bot_name")
    short = t(lang, "bot_short_description")
    description = t(lang, "bot_description", trial=days_count(lang, trial_days))
    if (await bot.get_my_name(language_code=language_code)).name != name:
        await bot.set_my_name(name=name, language_code=language_code)
    current_short = await bot.get_my_short_description(language_code=language_code)
    if current_short.short_description != short:
        await bot.set_my_short_description(short_description=short, language_code=language_code)
    if (await bot.get_my_description(language_code=language_code)).description != description:
        await bot.set_my_description(description=description, language_code=language_code)


async def setup_profile(bot: Bot, settings: Settings) -> None:
    targets: list[tuple[Language, str | None]] = [(Language.EN, None)]
    targets += [(Language.RU, code) for code in sorted(RUSSIAN_SPEAKING)]
    for lang, code in targets:
        try:
            await sync_profile(bot, lang, code, settings.trial_days)
        except TelegramAPIError as e:
            log.warning("Failed to update bot profile for language %s: %s", code or "default", e)


COMMANDS = ("day", "support", "paysupport", "privacy")


def commands(lang: Language) -> list[BotCommand]:
    return [BotCommand(command=c, description=t(lang, f"cmd_{c}")) for c in COMMANDS]


async def setup_defaults(bot: Bot, settings: Settings) -> None:
    await bot.set_my_commands(commands(Language.EN))
    for code in sorted(RUSSIAN_SPEAKING):
        await bot.set_my_commands(commands(Language.RU), language_code=code)
    if settings.webapp_url:
        await bot.set_chat_menu_button(menu_button=menu_button(Language.EN, settings))
    await setup_profile(bot, settings)


async def reset_chat_menu(bot: Bot, chat_id: int, lang: Language, settings: Settings) -> None:
    """Drops command lists set per chat by older versions so the default ones show."""
    await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=chat_id))
    if settings.webapp_url:
        await bot.set_chat_menu_button(chat_id=chat_id, menu_button=menu_button(lang, settings))
