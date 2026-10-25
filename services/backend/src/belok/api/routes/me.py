from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from belok.api.deps import CurrentUser, SessionDep
from belok.api.schemas import MeOut, ProfileIn, macros_out
from belok.db.models import User
from belok.domain.nutrition import daily_target
from belok.services.access import has_access
from belok.services.repo import latest_weight
from belok.services.users import update_profile
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


async def _me(session: AsyncSession, user: User) -> MeOut:
    weight = await latest_weight(session, user.id)
    age = local_today(user.timezone).year - user.birth_year if user.birth_year else None
    target = None
    if user.profile_complete and weight is not None:
        target = daily_target(user.sex, weight, user.height_cm, age, user.goal)
    return MeOut(
        id=user.id,
        username=user.username,
        profile_complete=user.profile_complete,
        sex=user.sex,
        age=age,
        height_cm=user.height_cm,
        goal=user.goal,
        weight_kg=weight,
        timezone=user.timezone,
        trial_ends_at=user.trial_ends_at,
        subscription_until=user.subscription_until,
        has_access=has_access(user, utcnow()),
        base_target=macros_out(target),
    )
