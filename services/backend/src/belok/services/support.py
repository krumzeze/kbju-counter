import logging
from datetime import timedelta
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot.texts import t
from belok.db.models import Payment, SupportMessage, SupportRelay, User
from belok.i18n import Language
from belok.services.payments import format_amount
from belok.timeutil import utcnow

log = logging.getLogger(__name__)

MAX_TEXT = 2000
DAILY_LIMIT = 20
REPLY_HINT = "Ответь на это сообщение, чтобы написать пользователю."


class TooManyMessages(Exception):
    pass


async def submit(
    session: AsyncSession, bot: Bot, user: User, text: str, source: str
) -> SupportMessage:
    """Stores a user's message and relays it to every admin. Commits."""
    since = utcnow() - timedelta(days=1)
    sent_today = await session.scalar(
        select(func.count())
        .select_from(SupportMessage)
        .where(
            SupportMessage.user_id == user.id,
            SupportMessage.from_admin.is_(False),
            SupportMessage.created_at >= since,
        )
    )
    if sent_today >= DAILY_LIMIT:
        raise TooManyMessages

    message = SupportMessage(user_id=user.id, from_admin=False, source=source, text=text[:MAX_TEXT])
    session.add(message)
    await session.flush()

    card = await _admin_card(session, user, message)
    admins = await session.scalars(
        select(User.id).where(User.is_admin.is_(True), User.bot_blocked.is_(False))
    )
    for admin_id in admins.all():
        try:
            sent = await bot.send_message(admin_id, card)
        except TelegramAPIError:
            log.warning("failed to relay support message to admin %s", admin_id, exc_info=True)
            continue
        session.add(
            SupportRelay(
                admin_chat_id=admin_id, admin_message_id=sent.message_id, message_id=message.id
            )
        )
    await session.commit()
    return message


async def reply(
    session: AsyncSession, bot: Bot, admin: User, chat_id: int, replied_to: int, text: str
) -> User | None:
    """Sends an admin's reply to the user behind a relayed message. Returns that user."""
    relay = await session.get(SupportRelay, (chat_id, replied_to))
    if relay is None:
        return None
    original = await session.get(SupportMessage, relay.message_id)
    user = await session.get(User, original.user_id)
    if user is None:
        return None
    lang = user.language or Language.RU
    await bot.send_message(user.id, t(lang, "support_reply", text=escape(text)))
    session.add(
        SupportMessage(
            user_id=user.id, from_admin=True, admin_id=admin.id, source="bot", text=text[:MAX_TEXT]
        )
    )
    await session.commit()
    return user


async def history(session: AsyncSession, user_id: int, limit: int = 100) -> list[SupportMessage]:
    rows = await session.scalars(
        select(SupportMessage)
        .where(SupportMessage.user_id == user_id)
        .order_by(SupportMessage.id.desc())
        .limit(limit)
    )
    return list(reversed(rows.all()))


async def recent_payments(session: AsyncSession, user_id: int, limit: int = 3) -> list[Payment]:
    rows = await session.scalars(
        select(Payment).where(Payment.user_id == user_id).order_by(Payment.id.desc()).limit(limit)
    )
    return list(rows.all())


async def _admin_card(session: AsyncSession, user: User, message: SupportMessage) -> str:
    who = escape(user.first_name or "")
    if user.username:
        who = f"{who} @{escape(user.username)}".strip()
    lines = [f"💬 <b>Поддержка</b> ({message.source}): {who} <code>{user.id}</code>"]
    payments = await recent_payments(session, user.id)
    if payments:
        lines.append(
            "Платежи: "
            + "; ".join(
                f"{p.created_at:%d.%m} {format_amount(p)}, {p.days} дн."
                + (" (возврат)" if p.refunded_at else "")
                for p in payments
            )
        )
    lines += ["", escape(message.text), "", f"<i>{REPLY_HINT}</i>"]
    return "\n".join(lines)
