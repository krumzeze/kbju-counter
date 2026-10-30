import secrets
from datetime import timedelta

from sqlalchemy import exists, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from belok.config import Settings
from belok.db.models import User
from belok.domain.nutrition import Goal, Sex
from belok.services.repo import upsert_weight
from belok.timeutil import local_today, utcnow

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
REFERRAL_PREFIX = "r_"
SEEN_RESOLUTION = timedelta(minutes=5)
# Serializes "first user becomes admin" between concurrent sign-ups.
ADMIN_BOOTSTRAP_LOCK = 72_017_001


def random_code(length: int) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


async def get_or_create_user(
    session: AsyncSession,
    settings: Settings,
    user_id: int,
    username: str | None,
    first_name: str | None,
    start_param: str | None = None,
) -> tuple[User, bool]:
    """Returns the user and whether it was just created."""
    user = await session.get(User, user_id)
    if user is not None:
        user.username = username or user.username
        user.first_name = first_name or user.first_name
        if user.referral_code is None:
            user.referral_code = random_code(8)
        if settings.admin_id == user.id:
            user.is_admin = True
        _touch(user)
        return user, False

    user = User(
        id=user_id,
        username=username,
        first_name=first_name,
        source=start_param[:64] if start_param else None,
        trial_ends_at=utcnow() + timedelta(days=settings.trial_days),
        timezone=settings.default_timezone,
        referral_code=random_code(8),
        last_seen_at=utcnow(),
    )
    if start_param and start_param.startswith(REFERRAL_PREFIX):
        user.referred_by_id = await session.scalar(
            select(User.id).where(
                User.referral_code == start_param.removeprefix(REFERRAL_PREFIX),
                User.is_blocked.is_(False),
            )
        )
        if user.referred_by_id is not None:
            user.trial_ends_at = utcnow() + timedelta(days=settings.referral_trial_days)
    user.is_admin = await _becomes_admin(session, settings, user_id)
    session.add(user)
    await session.flush()
    return user, True


async def _becomes_admin(session: AsyncSession, settings: Settings, user_id: int) -> bool:
    if settings.admin_id is not None:
        return settings.admin_id == user_id
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": ADMIN_BOOTSTRAP_LOCK})
    return not await session.scalar(select(exists().where(User.is_admin.is_(True))))


def _touch(user: User) -> None:
    now = utcnow()
    if user.last_seen_at is None or now - user.last_seen_at > SEEN_RESOLUTION:
        user.last_seen_at = now


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
