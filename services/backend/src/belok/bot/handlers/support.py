from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot.texts import t
from belok.db.models import User
from belok.i18n import Language
from belok.services import support
from belok.services.payments import format_amount

router = Router(name="support")


class SupportForm(StatesGroup):
    waiting = State()


@router.message(Command("support"))
async def cmd_support(message: Message, state: FSMContext, lang: Language) -> None:
    await state.set_state(SupportForm.waiting)
    await message.answer(t(lang, "support_ask"))


@router.message(Command("paysupport"))
async def cmd_paysupport(
    message: Message, state: FSMContext, session: AsyncSession, user: User, lang: Language
) -> None:
    await state.set_state(SupportForm.waiting)
    payments = await support.recent_payments(session, user.id)
    lines = [t(lang, "paysupport_ask")]
    if payments:
        lines.append("")
        lines.append(t(lang, "paysupport_payments"))
        lines += [f"• {p.created_at:%d.%m.%Y}: {format_amount(p)}" for p in payments]
    await message.answer("\n".join(lines))


@router.message(SupportForm.waiting, F.text & ~F.text.startswith("/"))
async def support_text(
    message: Message,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    user: User,
    lang: Language,
) -> None:
    await state.clear()
    try:
        await support.submit(session, bot, user, message.text, "bot")
    except support.TooManyMessages:
        await message.answer(t(lang, "support_too_many"))
        return
    await message.answer(t(lang, "support_sent"))


def is_admin_reply(message: Message, user: User, bot: Bot) -> bool:
    replied = message.reply_to_message
    return user.is_admin and replied.from_user is not None and replied.from_user.id == bot.id


@router.message(F.reply_to_message & F.text, is_admin_reply)
async def admin_reply(message: Message, bot: Bot, session: AsyncSession, user: User) -> None:
    try:
        target = await support.reply(
            session, bot, user, message.chat.id, message.reply_to_message.message_id, message.text
        )
    except TelegramAPIError:
        await message.reply("Не получилось отправить: пользователь, похоже, заблокировал бота.")
        return
    if target is None:
        await message.reply("Это не сообщение поддержки, ответить некому.")
        return
    await message.reply("✓ Отправлено")
