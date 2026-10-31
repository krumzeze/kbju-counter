import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import Payment, User
from belok.services.access import grant_days
from belok.services.referrals import reward_for_payment
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

    ref = f"tribute:{telegram_id}:{product_id}:{event.get('created_at')}"
    payment_id = await session.scalar(
        insert(Payment)
        .values(
            user_id=user.id,
            provider="tribute",
            external_ref=ref,
            product=str(product_id),
            amount=int(payload.get("amount") or 0),
            currency=str(payload.get("currency") or "").upper()[:8],
            days=plan.days,
        )
        .on_conflict_do_nothing(index_elements=["external_ref"])
        .returning(Payment.id)
    )
    if payment_id is None:
        return None
    grant_days(user, plan.days, utcnow())
    referrer = await reward_for_payment(session, user, ref, reward_days)
    payment = await session.get(Payment, payment_id)
    return PaymentOutcome(user=user, payment=payment, referrer=referrer)


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
    payment.refunded_at = utcnow()
    if user.subscription_until is not None:
        user.subscription_until -= timedelta(days=payment.days)
    return PaymentOutcome(user=user, payment=payment, refunded=True)
