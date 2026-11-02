import logging
from dataclasses import dataclass
from datetime import timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot.texts import payment_text
from belok.db.models import Payment, User
from belok.i18n import Language
from belok.services.access import grant_days
from belok.services.notify import notify_admins
from belok.services.referrals import reward_for_payment
from belok.services.stars import CURRENCY as STARS_CURRENCY
from belok.services.tribute import TributeCatalog
from belok.timeutil import utcnow

log = logging.getLogger(__name__)

PURCHASE = "new_digital_product"
REFUND = "digital_product_refund"


@dataclass(slots=True)
class PaymentOutcome:
    user: User
    payment: Payment
    refunded: bool = False
    referrer: User | None = None


async def handle_tribute_event(
    session: AsyncSession, catalog: TributeCatalog, event: dict, reward_days: int
) -> PaymentOutcome | None:
    """Apply a verified Tribute webhook. Returns None for events that change nothing."""
    name = event.get("name")
    payload = event.get("payload") or {}
    telegram_id = payload.get("telegram_user_id")
    product_id = payload.get("product_id")
    if name not in (PURCHASE, REFUND) or telegram_id is None or product_id is None:
        log.info("ignoring Tribute event %s", name)
        return None

    user = await session.get(User, int(telegram_id), with_for_update=True)
    if user is None:
        log.warning("Tribute event %s for unknown user %s", name, telegram_id)
        return None

    if name == REFUND:
        return await _refund(session, user, str(product_id))

    plan = await catalog.plan_for_product(int(product_id))
    if plan is None:
        log.warning("Tribute purchase of unknown product %s", product_id)
        return None

    return await record_payment(
        session,
        user,
        provider="tribute",
        ref=f"tribute:{telegram_id}:{product_id}:{event.get('created_at')}",
        product=str(product_id),
        amount=int(payload.get("amount") or 0),
        currency=str(payload.get("currency") or "").upper()[:8],
        days=plan.days,
        reward_days=reward_days,
    )


async def record_payment(
    session: AsyncSession,
    user: User,
    *,
    provider: str,
    ref: str,
    product: str,
    amount: int,
    currency: str,
    days: int,
    reward_days: int,
) -> PaymentOutcome | None:
    """Stores a payment once per ref and extends access. Returns None for duplicates."""
    payment_id = await session.scalar(
        insert(Payment)
        .values(
            user_id=user.id,
            provider=provider,
            external_ref=ref,
            product=product,
            amount=amount,
            currency=currency,
            days=days,
        )
        .on_conflict_do_nothing(index_elements=["external_ref"])
        .returning(Payment.id)
    )
    if payment_id is None:
        return None
    grant_days(user, days, utcnow())
    referrer = await reward_for_payment(session, user, ref, reward_days)
    payment = await session.get(Payment, payment_id)
    return PaymentOutcome(user=user, payment=payment, referrer=referrer)


async def refund_by_ref(session: AsyncSession, user: User, ref: str) -> PaymentOutcome | None:
    payment = await session.scalar(
        select(Payment)
        .where(Payment.external_ref == ref, Payment.refunded_at.is_(None))
        .with_for_update()
    )
    if payment is None:
        return None
    return _apply_refund(user, payment)


def format_amount(payment: Payment) -> str:
    if payment.currency == STARS_CURRENCY:
        return f"{payment.amount} ⭐"
    return f"{payment.amount / 100:g} {payment.currency}"


async def announce(bot: Bot, session: AsyncSession, outcome: PaymentOutcome) -> None:
    user, payment = outcome.user, outcome.payment
    lang = user.language or Language.RU
    try:
        await bot.send_message(user.id, payment_text(lang, user, payment, outcome.refunded))
    except TelegramAPIError:
        log.warning("failed to notify user %s about payment", user.id, exc_info=True)
    kind = "Возврат" if outcome.refunded else "Оплата"
    who = f"@{user.username}" if user.username else str(user.id)
    await notify_admins(
        bot,
        session,
        "payments",
        f"💳 {kind}: {who}, {format_amount(payment)}, {payment.days} дн.",
    )


async def _refund(session: AsyncSession, user: User, product: str) -> PaymentOutcome | None:
    payment = await session.scalar(
        select(Payment)
        .where(
            Payment.user_id == user.id,
            Payment.product == product,
            Payment.refunded_at.is_(None),
        )
        .order_by(Payment.id.desc())
        .limit(1)
        .with_for_update()
    )
    if payment is None:
        return None
    return _apply_refund(user, payment)


def _apply_refund(user: User, payment: Payment) -> PaymentOutcome:
    payment.refunded_at = utcnow()
    if user.subscription_until is not None:
        user.subscription_until -= timedelta(days=payment.days)
    return PaymentOutcome(user=user, payment=payment, refunded=True)
