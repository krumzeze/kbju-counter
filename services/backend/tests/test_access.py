from datetime import UTC, datetime, timedelta

from belok.db.models import User
from belok.services.access import AccessStatus, access_status, grant_days, has_access

NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)


def make_user(trial_delta: timedelta, subscription_delta: timedelta | None = None) -> User:
    return User(
        id=1,
        trial_ends_at=NOW + trial_delta,
        subscription_until=NOW + subscription_delta if subscription_delta is not None else None,
        timezone="UTC",
    )


def test_active_trial_grants_access():
    assert has_access(make_user(timedelta(days=2)), NOW)


def test_expired_trial_without_subscription_denies_access():
    assert not has_access(make_user(timedelta(seconds=-1)), NOW)


def test_active_subscription_after_trial_grants_access():
    assert has_access(make_user(timedelta(days=-10), timedelta(days=5)), NOW)


def test_expired_subscription_denies_access():
    assert not has_access(make_user(timedelta(days=-10), timedelta(days=-1)), NOW)


def test_lifetime_access_ignores_dates():
    user = make_user(timedelta(days=-10))
    user.lifetime_access = True
    assert access_status(user, NOW) == AccessStatus.LIFETIME


def test_grant_extends_from_end_of_trial():
    user = make_user(timedelta(days=2))
    grant_days(user, 7, NOW)
    assert user.subscription_until == NOW + timedelta(days=9)
    assert access_status(user, NOW) == AccessStatus.ACTIVE


def test_grant_after_expiry_starts_now():
    user = make_user(timedelta(days=-10), timedelta(days=-3))
    grant_days(user, 7, NOW)
    assert user.subscription_until == NOW + timedelta(days=7)
