import json
import logging

from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, HTTPException, Request, Response, status

from belok.api.deps import BotDep, CurrentUser, SessionDep, SettingsDep, TributeDep
from belok.api.schemas import PlanOut
from belok.bot.texts import payment_text
from belok.i18n import Language
from belok.services.notify import notify_admins
from belok.services.payments import handle_tribute_event
from belok.services.tribute import signature_valid

log = logging.getLogger(__name__)

router = APIRouter(tags=["payments"])


@router.get("/payments/plans")
async def get_plans(user: CurrentUser, tribute: TributeDep) -> list[PlanOut]:
    if not tribute.enabled:
        return []
    return [
        PlanOut(
            code=p.code,
            days=p.days,
            link=p.link,
            web_link=p.web_link,
            amount=p.amount,
            currency=p.currency,
        )
        for p in await tribute.plans()
    ]


@router.post("/payments/tribute", include_in_schema=False)
async def tribute_webhook(
    request: Request, session: SessionDep, settings: SettingsDep, tribute: TributeDep, bot: BotDep
) -> Response:
    if not tribute.api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "payments_disabled")
    body = await request.body()
    if not signature_valid(body, request.headers.get("trbt-signature"), tribute.api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_signature")
    try:
        event = json.loads(body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_json") from exc

    outcome = await handle_tribute_event(session, tribute, event, settings.referral_reward_days)
    await session.commit()
    if outcome is None:
        return Response(status_code=status.HTTP_200_OK)

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
        f"💳 {kind}: {who}, {payment.amount / 100:g} {payment.currency}, {payment.days} дн.",
    )
    return Response(status_code=status.HTTP_200_OK)
