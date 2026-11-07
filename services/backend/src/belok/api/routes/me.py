from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from belok.api.deps import CurrentUser, PhotosDep, SessionDep, SettingsDep
from belok.api.schemas import (
    AdaptiveOut,
    LanguageIn,
    MeOut,
    ProfileIn,
    PromoRedeemIn,
    PromoRedeemOut,
    ReferralOut,
    SettingsIn,
    macros_out,
)
from belok.config import Settings
from belok.db.models import User
from belok.domain.nutrition import daily_target, maintenance_kcal
from belok.services import features
from belok.services.access import access_status, access_until, has_access
from belok.services.meals import analyses_left, drop_eval_photos
from belok.services.promos import PromoResult, redeem
from belok.services.referrals import referral_stats
from belok.services.repo import latest_weight
from belok.services.targets import adaptive_estimate
from belok.services.users import REFERRAL_PREFIX, update_profile
from belok.services.workouts import activity_kcal
from belok.timeutil import local_today, utcnow

router = APIRouter(tags=["me"])


@router.get("/me")
async def get_me(user: CurrentUser, session: SessionDep, settings: SettingsDep) -> MeOut:
    return await _me(session, user, settings)


@router.put("/me/profile")
async def put_profile(
    body: ProfileIn, user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> MeOut:
    if body.timezone:
        user.timezone = body.timezone
    await update_profile(
        session, user, body.sex, body.age, body.height_cm, body.weight_kg, body.goal
    )
    await session.commit()
    return await _me(session, user, settings)


@router.put("/me/language")
async def put_language(
    body: LanguageIn, user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> MeOut:
    user.language = body.language
    await session.commit()
    return await _me(session, user, settings)


@router.patch("/me/settings")
async def patch_settings(
    body: SettingsIn,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    photos: PhotosDep,
) -> MeOut:
    if body.adaptive_target and not user.adaptive_target:
        if not has_access(user, utcnow()):
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "premium_required")
        info = await _adaptive(session, user)
        if info is None or not info.ready:
            raise HTTPException(status.HTTP_409_CONFLICT, "adaptive_not_ready")
    if body.photo_eval_consent is False and user.photo_eval_consent:
        await drop_eval_photos(session, photos, user)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await session.commit()
    return await _me(session, user, settings)


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


async def _me(session: AsyncSession, user: User, settings: Settings) -> MeOut:
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
        activity_adjust=user.activity_adjust,
        adaptive_target=user.adaptive_target,
        remind_meals=user.remind_meals,
        remind_weight=user.remind_weight,
        photo_eval_consent=user.photo_eval_consent,
        photo_storage=settings.photos_enabled,
        adaptive=await _adaptive(session, user, weight),
        base_target=macros_out(target),
        features={key.value: on for key, on in (await features.flags(session)).items()},
        analyses_left=await analyses_left(session, user, settings),
        free_history_days=settings.free_history_days,
    )


async def _adaptive(
    session: AsyncSession, user: User, weight: float | None = None
) -> AdaptiveOut | None:
    weight = weight or await latest_weight(session, user.id)
    if not user.profile_complete or weight is None:
        return None
    today = local_today(user.timezone)
    activity = await activity_kcal(session, user.id, today, weight)
    formula = maintenance_kcal(
        user.sex, weight, user.height_cm, today.year - user.birth_year, activity
    )
    estimate = await adaptive_estimate(session, user.id, today, formula)
    return AdaptiveOut(
        ready=estimate.ready,
        logged_days=estimate.logged_days,
        weigh_ins=estimate.weigh_ins,
        span_days=estimate.span_days,
        tdee=estimate.tdee,
        formula_tdee=formula,
    )
