import logging

from aiogram import Bot, F, Router
from aiogram.types import Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot.texts import t
from belok.config import Settings
from belok.db.models import User
from belok.i18n import Language
from belok.services import features, stars
from belok.services.features import Feature
from belok.services.payments import announce, record_payment, refund_by_ref

log = logging.getLogger(__name__)

router = Router(name="payments")


def _ref(charge_id: str) -> str:
    return f"stars:{charge_id}"


@router.pre_checkout_query()
async def pre_checkout(
    query: PreCheckoutQuery, session: AsyncSession, settings: Settings, lang: Language
) -> None:
    plan = stars.plan_for_payload(
        stars.parse_plans(settings.stars_plans), query.invoice_payload, query.total_amount
    )
    if (
        query.currency != stars.CURRENCY
        or plan is None
        or not await features.enabled(session, Feature.PAYMENTS)
    ):
        await query.answer(ok=False, error_message=t(lang, "stars_unavailable"))
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(
    message: Message, bot: Bot, session: AsyncSession, user: User, settings: Settings
) -> None:
    payment = message.successful_payment
    if payment.currency != stars.CURRENCY:
        return
    days = _days_from_payload(payment.invoice_payload)
    if days is None:
        log.error("Stars payment %s with unknown payload", payment.telegram_payment_charge_id)
        return
    outcome = await record_payment(
        session,
        user,
        provider="stars",
        ref=_ref(payment.telegram_payment_charge_id),
        product=f"stars-{days}",
        amount=payment.total_amount,
        currency=stars.CURRENCY,
        days=days,
        reward_days=settings.referral_reward_days,
    )
    await session.commit()
    if outcome is not None:
        await announce(bot, session, outcome)


@router.message(F.refunded_payment)
async def refunded_payment(message: Message, bot: Bot, session: AsyncSession, user: User) -> None:
    refund = message.refunded_payment
    outcome = await refund_by_ref(session, user, _ref(refund.telegram_payment_charge_id))
    await session.commit()
    if outcome is not None:
        await announce(bot, session, outcome)


def _days_from_payload(payload: str) -> int | None:
    days, _, _ = payload.removeprefix(stars.PAYLOAD_PREFIX).partition(":")
    return int(days) if payload.startswith(stars.PAYLOAD_PREFIX) and days.isdigit() else None
