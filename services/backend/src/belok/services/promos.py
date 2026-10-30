import re
from datetime import timedelta
from enum import StrEnum

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import PromoAttempt, PromoCode, PromoRedemption, User
from belok.services.access import grant_days
from belok.services.users import random_code
from belok.timeutil import utcnow

PROMO_PREFIX = "p_"
CODE_PATTERN = re.compile(r"^[A-Z0-9_-]{3,32}$")
MAX_FAILED_ATTEMPTS = 5
ATTEMPT_WINDOW = timedelta(hours=1)
NEW_USER_WINDOW = timedelta(days=7)


class PromoResult(StrEnum):
    OK = "ok"
    NOT_FOUND = "not_found"
    EXPIRED = "expired"
    EXHAUSTED = "exhausted"
    ALREADY_USED = "already_used"
    NEW_USERS_ONLY = "new_users_only"
    TOO_MANY_ATTEMPTS = "too_many_attempts"


def normalize_code(code: str) -> str:
    return code.strip().upper()


def generate_code() -> str:
    return random_code(10)


async def redeem(session: AsyncSession, user: User, raw_code: str) -> tuple[PromoResult, int]:
    """Apply a promo code. Returns the outcome and the number of granted days."""
    now = utcnow()
    failed = await session.scalar(
        select(func.count())
        .select_from(PromoAttempt)
        .where(PromoAttempt.user_id == user.id, PromoAttempt.created_at > now - ATTEMPT_WINDOW)
    )
    if failed >= MAX_FAILED_ATTEMPTS:
        return PromoResult.TOO_MANY_ATTEMPTS, 0

    code = normalize_code(raw_code)
    promo = None
    if CODE_PATTERN.fullmatch(code):
        promo = await session.scalar(
            select(PromoCode).where(PromoCode.code == code, PromoCode.active.is_(True))
        )
    if promo is None:
        session.add(PromoAttempt(user_id=user.id))
        return PromoResult.NOT_FOUND, 0
    if promo.expires_at is not None and promo.expires_at <= now:
        return PromoResult.EXPIRED, 0
    if promo.new_users_only and now - user.created_at > NEW_USER_WINDOW:
        return PromoResult.NEW_USERS_ONLY, 0

    try:
        async with session.begin_nested():
            session.add(PromoRedemption(promo_id=promo.id, user_id=user.id))
            await session.flush()
            claimed = await session.scalar(
                update(PromoCode)
                .where(
                    PromoCode.id == promo.id,
                    or_(
                        PromoCode.max_activations.is_(None),
                        PromoCode.activations < PromoCode.max_activations,
                    ),
                )
                .values(activations=PromoCode.activations + 1)
                .returning(PromoCode.id)
            )
            if claimed is None:
                raise _Exhausted
    except IntegrityError:
        return PromoResult.ALREADY_USED, 0
    except _Exhausted:
        return PromoResult.EXHAUSTED, 0

    grant_days(user, promo.days, now)
    return PromoResult.OK, promo.days


class _Exhausted(Exception):
    pass
