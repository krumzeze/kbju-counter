from datetime import timedelta

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from belok.api import admin_schemas as s
from belok.api.deps import AdminUser, BotDep, SessionDep, SettingsDep
from belok.api.schemas import MealOut
from belok.config import Settings
from belok.db.models import (
    AdminAction,
    Broadcast,
    PromoCode,
    PromoRedemption,
    ReferralReward,
    User,
)
from belok.services import admin_users, stats
from belok.services.access import access_status, access_until, grant_days
from belok.services.audit import log_action
from belok.services.broadcasts import segment_size
from belok.services.notify import admin_prefs
from belok.services.promos import PROMO_PREFIX, generate_code
from belok.services.referrals import referral_stats
from belok.services.repo import latest_weight
from belok.timeutil import local_today, utcnow

router = APIRouter(prefix="/admin", tags=["admin"])

ACTIVITY_DAYS = 30


@router.get("/dashboard")
async def dashboard(admin: AdminUser, session: SessionDep, settings: SettingsDep) -> s.DashboardOut:
    d = await stats.dashboard(session, utcnow(), settings.default_timezone)
    return s.DashboardOut(
        **{
            k: getattr(d, k)
            for k in s.DashboardOut.model_fields
            if k not in {"funnel", "sources", "series"}
        },
        funnel=[s.CountOut(key=k, count=n) for k, n in d.funnel],
        sources=[s.CountOut(key=k, count=n) for k, n in d.sources],
        series=[s.DayPointOut.model_validate(p) for p in d.series],
    )


@router.get("/users")
async def list_users(
    admin: AdminUser,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=64),
    filter: admin_users.UserFilter = admin_users.UserFilter.ALL,
    sort: admin_users.UserSort = admin_users.UserSort.CREATED,
    desc: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> s.UserPageOut:
    rows, total = await admin_users.list_users(
        session, utcnow(), q, filter, sort, desc, offset, limit
    )
    return s.UserPageOut(
        items=[_row(r.user, r.status, r.analyses, r.cost_usd) for r in rows], total=total
    )


@router.get("/users/{user_id}")
async def get_user(
    user_id: int, admin: AdminUser, session: SessionDep, settings: SettingsDep
) -> s.UserDetailOut:
    return await _detail(session, settings, await _get_user(session, user_id))


@router.patch("/users/{user_id}")
async def patch_user(
    user_id: int,
    body: s.UserPatchIn,
    admin: AdminUser,
    session: SessionDep,
    settings: SettingsDep,
) -> s.UserDetailOut:
    user = await _get_user(session, user_id)
    changes = body.model_dump(exclude_unset=True)
    if user.id == admin.id and (changes.get("is_blocked") or changes.get("is_admin") is False):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_change_self")
    if changes.get("is_blocked") and user.is_admin:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_block_admin")
    for field, value in changes.items():
        if getattr(user, field) != value:
            log_action(session, admin, f"set_{field}", user.id, old=getattr(user, field), new=value)
            setattr(user, field, value)
    await session.commit()
    return await _detail(session, settings, user)


@router.post("/users/{user_id}/grant")
async def grant(
    user_id: int, body: s.GrantIn, admin: AdminUser, session: SessionDep, settings: SettingsDep
) -> s.UserDetailOut:
    user = await _get_user(session, user_id)
    grant_days(user, body.days, utcnow())
    log_action(
        session,
        admin,
        "grant_days",
        user.id,
        days=body.days,
        until=user.subscription_until.isoformat(),
    )
    await session.commit()
    return await _detail(session, settings, user)


@router.post("/users/{user_id}/revoke")
async def revoke(
    user_id: int, admin: AdminUser, session: SessionDep, settings: SettingsDep
) -> s.UserDetailOut:
    user = await _get_user(session, user_id)
    now = utcnow()
    user.lifetime_access = False
    user.subscription_until = None
    user.trial_ends_at = min(user.trial_ends_at, now)
    log_action(session, admin, "revoke_access", user.id)
    await session.commit()
    return await _detail(session, settings, user)


@router.post("/users/{user_id}/message", status_code=status.HTTP_204_NO_CONTENT)
async def message_user(
    user_id: int, body: s.MessageIn, admin: AdminUser, session: SessionDep, bot: BotDep
) -> Response:
    user = await _get_user(session, user_id)
    await _send(bot, user.id, body.text)
    log_action(session, admin, "message", user.id, text=body.text[:500])
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, admin: AdminUser, session: SessionDep) -> Response:
    user = await _get_user(session, user_id)
    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_change_self")
    log_action(session, admin, "delete_user", user.id, username=user.username)
    await session.execute(delete(User).where(User.id == user.id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/promos")
async def list_promos(
    admin: AdminUser, session: SessionDep, settings: SettingsDep
) -> list[s.PromoOut]:
    retained = (
        select(PromoRedemption.promo_id, func.count().label("n"))
        .join(User, User.id == PromoRedemption.user_id)
        .where(User.last_seen_at >= utcnow() - admin_users.INACTIVE_AFTER)
        .group_by(PromoRedemption.promo_id)
        .subquery()
    )
    rows = await session.execute(
        select(PromoCode, func.coalesce(retained.c.n, 0))
        .outerjoin(retained, retained.c.promo_id == PromoCode.id)
        .order_by(PromoCode.created_at.desc())
    )
    return [_promo(p, n, settings) for p, n in rows.all()]


@router.post("/promos", status_code=status.HTTP_201_CREATED)
async def create_promo(
    body: s.PromoIn, admin: AdminUser, session: SessionDep, settings: SettingsDep
) -> s.PromoOut:
    promo = PromoCode(
        code=body.code or generate_code(),
        days=body.days,
        max_activations=body.max_activations,
        expires_at=body.expires_at,
        new_users_only=body.new_users_only,
        note=body.note,
        created_by_id=admin.id,
        active=True,
        activations=0,
    )
    session.add(promo)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "code_taken") from exc
    log_action(session, admin, "create_promo", code=promo.code, days=promo.days)
    await session.commit()
    return _promo(promo, 0, settings)


@router.patch("/promos/{promo_id}")
async def patch_promo(
    promo_id: int,
    body: s.PromoPatchIn,
    admin: AdminUser,
    session: SessionDep,
    settings: SettingsDep,
) -> s.PromoOut:
    promo = await session.get(PromoCode, promo_id)
    if promo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(promo, field, value)
    log_action(
        session, admin, "update_promo", code=promo.code, **{k: str(v) for k, v in changes.items()}
    )
    await session.commit()
    return _promo(promo, 0, settings)


@router.get("/segments")
async def segments(admin: AdminUser, session: SessionDep) -> list[s.CountOut]:
    return [
        s.CountOut(key=segment.value, count=await segment_size(session, segment))
        for segment in admin_users.Segment
    ]


@router.get("/broadcasts")
async def list_broadcasts(admin: AdminUser, session: SessionDep) -> list[s.BroadcastOut]:
    result = await session.scalars(select(Broadcast).order_by(Broadcast.id.desc()).limit(50))
    return [s.BroadcastOut.model_validate(b) for b in result]


@router.post("/broadcasts", status_code=status.HTTP_201_CREATED)
async def create_broadcast(
    body: s.BroadcastIn, admin: AdminUser, session: SessionDep, bot: BotDep
) -> s.BroadcastOut:
    await _send(bot, admin.id, body.text)
    broadcast = Broadcast(
        created_by_id=admin.id,
        text=body.text,
        segment=body.segment.value,
        status="draft",
        cursor=0,
        total=await segment_size(session, body.segment),
        sent=0,
        failed=0,
        blocked=0,
    )
    session.add(broadcast)
    await session.commit()
    return s.BroadcastOut.model_validate(broadcast)


@router.post("/broadcasts/{broadcast_id}/send")
async def send_broadcast(
    broadcast_id: int, admin: AdminUser, session: SessionDep
) -> s.BroadcastOut:
    broadcast = await _transition(session, broadcast_id, {"draft"}, "sending")
    broadcast.total = await segment_size(session, admin_users.Segment(broadcast.segment))
    broadcast.started_at = utcnow()
    log_action(
        session, admin, "send_broadcast", broadcast_id=broadcast.id, segment=broadcast.segment
    )
    await session.commit()
    return s.BroadcastOut.model_validate(broadcast)


@router.post("/broadcasts/{broadcast_id}/cancel")
async def cancel_broadcast(
    broadcast_id: int, admin: AdminUser, session: SessionDep
) -> s.BroadcastOut:
    broadcast = await _transition(session, broadcast_id, {"draft", "sending"}, "cancelled")
    broadcast.finished_at = utcnow()
    log_action(session, admin, "cancel_broadcast", broadcast_id=broadcast.id)
    await session.commit()
    return s.BroadcastOut.model_validate(broadcast)


@router.get("/referrals")
async def top_referrers(admin: AdminUser, session: SessionDep) -> list[s.ReferrerOut]:
    referrer = aliased(User)
    invited = (
        select(User.referred_by_id.label("id"), func.count().label("invited"))
        .where(User.referred_by_id.is_not(None))
        .group_by(User.referred_by_id)
        .subquery()
    )
    rewards = (
        select(
            ReferralReward.referrer_id.label("id"),
            func.count(func.distinct(ReferralReward.referred_id)).label("paid"),
            func.sum(ReferralReward.days).label("days"),
        )
        .group_by(ReferralReward.referrer_id)
        .subquery()
    )
    rows = await session.execute(
        select(
            referrer,
            invited.c.invited,
            func.coalesce(rewards.c.paid, 0),
            func.coalesce(rewards.c.days, 0),
        )
        .join(invited, invited.c.id == referrer.id)
        .outerjoin(rewards, rewards.c.id == referrer.id)
        .order_by(invited.c.invited.desc())
        .limit(50)
    )
    return [
        s.ReferrerOut(**_brief(u).model_dump(), invited=i, paid=p, days=d)
        for u, i, p, d in rows.all()
    ]


@router.get("/actions")
async def actions(
    admin: AdminUser,
    session: SessionDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[s.ActionOut]:
    result = await session.scalars(
        select(AdminAction).order_by(AdminAction.created_at.desc()).offset(offset).limit(limit)
    )
    return await _actions(session, list(result))


@router.get("/prefs")
async def get_prefs(admin: AdminUser) -> s.PrefsOut:
    return s.PrefsOut(**admin_prefs(admin))


@router.put("/prefs")
async def put_prefs(body: s.PrefsIn, admin: AdminUser, session: SessionDep) -> s.PrefsOut:
    admin.admin_prefs = admin_prefs(admin) | body.model_dump(exclude_none=True)
    await session.commit()
    return s.PrefsOut(**admin_prefs(admin))


async def _get_user(session: SessionDep, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return user


async def _send(bot: BotDep, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text)
    except TelegramBadRequest as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_message") from exc
    except TelegramAPIError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "telegram_unavailable") from exc


async def _transition(
    session: SessionDep, broadcast_id: int, allowed: set[str], target: str
) -> Broadcast:
    updated = await session.scalar(
        update(Broadcast)
        .where(Broadcast.id == broadcast_id, Broadcast.status.in_(allowed))
        .values(status=target)
        .returning(Broadcast.id)
    )
    broadcast = await session.get(Broadcast, broadcast_id, populate_existing=True)
    if broadcast is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if updated is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_state")
    return broadcast


def _brief(user: User) -> s.UserBriefOut:
    return s.UserBriefOut(id=user.id, username=user.username, first_name=user.first_name)


def _row(user: User, status_name: str, analyses: int, cost: float) -> s.UserRowOut:
    return s.UserRowOut(
        **_brief(user).model_dump(),
        created_at=user.created_at,
        last_seen_at=user.last_seen_at,
        status=status_name,
        access_until=access_until(user),
        analyses=analyses,
        cost_usd=cost,
        is_admin=user.is_admin,
        is_blocked=user.is_blocked,
        bot_blocked=user.bot_blocked,
    )


def _promo(promo: PromoCode, retained: int, settings: Settings) -> s.PromoOut:
    link = None
    if settings.bot_username:
        link = f"https://t.me/{settings.bot_username}?start={PROMO_PREFIX}{promo.code}"
    return s.PromoOut(
        id=promo.id,
        code=promo.code,
        days=promo.days,
        max_activations=promo.max_activations,
        activations=promo.activations,
        expires_at=promo.expires_at,
        new_users_only=promo.new_users_only,
        active=promo.active,
        note=promo.note,
        created_at=promo.created_at,
        retained=retained,
        link=link,
    )


async def _actions(session: SessionDep, items: list[AdminAction]) -> list[s.ActionOut]:
    ids = {a.admin_id for a in items} | {a.target_user_id for a in items}
    ids.discard(None)
    users = (
        {u.id: u for u in await session.scalars(select(User).where(User.id.in_(ids)))}
        if ids
        else {}
    )
    return [
        s.ActionOut(
            id=a.id,
            created_at=a.created_at,
            action=a.action,
            admin=_brief(users[a.admin_id]) if a.admin_id in users else None,
            target=_brief(users[a.target_user_id]) if a.target_user_id in users else None,
            target_user_id=a.target_user_id,
            details=a.details,
        )
        for a in items
    ]


async def _detail(session: SessionDep, settings: Settings, user: User) -> s.UserDetailOut:
    now = utcnow()
    today = local_today(user.timezone)
    requests, errors, cost = await admin_users.llm_totals(session, user.id)
    analyses = requests - errors
    invited, paid, days = await referral_stats(session, user.id)
    referred_by = await session.get(User, user.referred_by_id) if user.referred_by_id else None
    return s.UserDetailOut(
        **_row(user, access_status(user, now).value, analyses, cost).model_dump(),
        source=user.source,
        timezone=user.timezone,
        sex=user.sex,
        age=today.year - user.birth_year if user.birth_year else None,
        height_cm=user.height_cm,
        goal=user.goal,
        weight_kg=await latest_weight(session, user.id),
        trial_ends_at=user.trial_ends_at,
        subscription_until=user.subscription_until,
        lifetime_access=bool(user.lifetime_access),
        daily_limit=user.daily_limit,
        llm_errors=errors,
        llm_requests=requests,
        referred_by=_brief(referred_by) if referred_by else None,
        invited=invited,
        invited_paid=paid,
        referral_days=days,
        activity=[
            s.ActivityDayOut.model_validate(a)
            for a in await admin_users.activity(
                session, user.id, today - timedelta(days=ACTIVITY_DAYS - 1), today
            )
        ],
        meals=[MealOut.of(m) for m in await admin_users.recent_meals(session, user.id, 20)],
        llm=[
            s.LlmCallOut.model_validate(c)
            for c in await admin_users.recent_llm(session, user.id, 30)
        ],
        redemptions=[
            s.RedemptionOut(code=c, days=d, created_at=t)
            for c, d, t in await admin_users.redemptions(session, user.id)
        ],
        actions=await _actions(session, await admin_users.actions_on(session, user.id, 30)),
    )
