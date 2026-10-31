from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from belok.api.deps import CurrentUser, SessionDep, SettingsDep
from belok.api.schemas import (
    LanguageIn,
    MeOut,
    ProfileIn,
    PromoRedeemIn,
    PromoRedeemOut,
    ReferralOut,
    macros_out,
)
from belok.db.models import User
from belok.domain.nutrition import daily_target
from belok.services.access import access_status, access_until, has_access
from belok.services.promos import PromoResult, redeem
from belok.services.referrals import referral_stats
from belok.services.repo import latest_weight
from belok.services.users import REFERRAL_PREFIX, update_profile
from belok.timeutil import local_today, utcnow

router = APIRouter(tags=["me"])


@router.get("/me")
async def get_me(user: CurrentUser, session: SessionDep) -> MeOut:
    return await _me(session, user)


@router.put("/me/profile")
async def put_profile(body: ProfileIn, user: CurrentUser, session: SessionDep) -> MeOut:
    if body.timezone:
        user.timezone = body.timezone
    await update_profile(
        session, user, body.sex, body.age, body.height_cm, body.weight_kg, body.goal
    )
    await session.commit()
    return await _me(session, user)


@router.put("/me/language")
async def put_language(body: LanguageIn, user: CurrentUser, session: SessionDep) -> MeOut:
    user.language = body.language
    await session.commit()
    return await _me(session, user)


@router.post("/me/promo")
async def redeem_promo(
    body: PromoRedeemIn, user: CurrentUser, session: SessionDep
) -> PromoRedeemOut:
    result, days = await redeem(session, user, body.code)
    await session.commit()
    if result != PromoResult.OK:
        code = status.HTTP_429_TOO_MANY_REQUESTS if result == PromoResult.TOO_MANY_ATTEMPTS else 400
        raise HTTPException(code, result.value)
    return PromoRedeemOut(days=days, access_until=access_until(user))


@router.get("/me/referral")
async def get_referral(
    user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> ReferralOut:
    invited, paid, days = await referral_stats(session, user.id)
    link = None
    if settings.bot_username:
        link = f"https://t.me/{settings.bot_username}?start={REFERRAL_PREFIX}{user.referral_code}"
    return ReferralOut(
        link=link,
        invited=invited,
        paid=paid,
        days=days,
        trial_days=settings.referral_trial_days,
        reward_days=settings.referral_reward_days,
    )


async def _me(session: AsyncSession, user: User) -> MeOut:
    weight = await latest_weight(session, user.id)
    age = local_today(user.timezone).year - user.birth_year if user.birth_year else None
    target = None
    if user.profile_complete and weight is not None:
        target = daily_target(user.sex, weight, user.height_cm, age, user.goal)
    return MeOut(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        profile_complete=user.profile_complete,
        sex=user.sex,
        age=age,
        height_cm=user.height_cm,
        goal=user.goal,
        weight_kg=weight,
        timezone=user.timezone,
        language=user.language,
        trial_ends_at=user.trial_ends_at,
        subscription_until=user.subscription_until,
        has_access=has_access(user, utcnow()),
        status=access_status(user, utcnow()).value,
        access_until=access_until(user),
        is_admin=user.is_admin,
        base_target=macros_out(target),
    )
