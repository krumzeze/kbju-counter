from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot import texts
from belok.config import Settings
from belok.db.models import User
from belok.services.monitor import summary_text
from belok.timeutil import utcnow

router = Router(name="admin")


@router.message(Command("admin"))
async def cmd_admin(
    message: Message, session: AsyncSession, user: User, settings: Settings
) -> None:
    if not user.is_admin:
        await message.answer(texts.HELP)
        return
    markup = None
    if settings.webapp_url:
        url = settings.webapp_url.rstrip("/") + "/admin"
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Открыть админку", web_app=WebAppInfo(url=url))]
            ]
        )
    await message.answer(
        await summary_text(session, utcnow(), settings.default_timezone), reply_markup=markup
    )
