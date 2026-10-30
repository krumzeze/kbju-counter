from datetime import datetime, timedelta
from enum import StrEnum

from belok.db.models import User


class AccessStatus(StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    LIFETIME = "lifetime"
    EXPIRED = "expired"


def access_status(user: User, now: datetime) -> AccessStatus:
    if user.lifetime_access:
        return AccessStatus.LIFETIME
    if user.subscription_until is not None and now < user.subscription_until:
        return AccessStatus.ACTIVE
    if now < user.trial_ends_at:
        return AccessStatus.TRIAL
    return AccessStatus.EXPIRED


def has_access(user: User, now: datetime) -> bool:
    return access_status(user, now) != AccessStatus.EXPIRED


def access_until(user: User) -> datetime:
    if user.subscription_until is None:
        return user.trial_ends_at
    return max(user.trial_ends_at, user.subscription_until)


def grant_days(user: User, days: int, now: datetime) -> None:
    """Extend access by `days`, starting from whenever the current access ends."""
    user.subscription_until = max(now, access_until(user)) + timedelta(days=days)
