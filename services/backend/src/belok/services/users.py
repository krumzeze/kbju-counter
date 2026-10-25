from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import User
from belok.domain.nutrition import Goal, Sex
from belok.services.repo import upsert_weight
from belok.timeutil import local_today, utcnow


async def get_or_create_user(
    session: AsyncSession, user_id: int, username: str | None, trial_days: int, timezone: str
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        user = User(
            id=user_id,
            username=username,
            trial_ends_at=utcnow() + timedelta(days=trial_days),
            timezone=timezone,
        )
        session.add(user)
        await session.flush()
    elif username and user.username != username:
        user.username = username
    return user


async def update_profile(
    session: AsyncSession,
    user: User,
    sex: Sex,
    age: int,
    height_cm: int,
    weight_kg: float,
    goal: Goal,
) -> None:
    today = local_today(user.timezone)
    user.sex = sex
    user.birth_year = today.year - age
    user.height_cm = height_cm
    user.goal = goal
    await upsert_weight(session, user.id, today, weight_kg)
