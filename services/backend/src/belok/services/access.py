from datetime import datetime

from belok.db.models import User


def has_access(user: User, now: datetime) -> bool:
    if now < user.trial_ends_at:
        return True
    return user.subscription_until is not None and now < user.subscription_until
