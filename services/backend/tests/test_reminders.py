from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from belok.db.models import Meal, User
from belok.services.reminders import (
    MIN_DAYS,
    SCHEDULE,
    Reminder,
    personal_schedule,
    send_due,
    usual_meal_minutes,
)
from belok.timeutil import utcnow
from tests.conftest import onboarded

MSK = ZoneInfo("Europe/Moscow")


def test_schedule_without_history_is_fixed():
    assert personal_schedule({}) == SCHEDULE


def test_schedule_follows_usual_time_with_grace():
    schedule = personal_schedule({Reminder.LUNCH: 12 * 60 + 2, Reminder.DINNER: 19 * 60})
    assert schedule[Reminder.LUNCH] == time(12, 45)
    assert schedule[Reminder.DINNER] == time(19, 45)
    assert schedule[Reminder.WEIGHT] == SCHEDULE[Reminder.WEIGHT]


def test_schedule_is_clamped():
    schedule = personal_schedule({Reminder.LUNCH: 11 * 60, Reminder.DINNER: 23 * 60 + 30})
    assert schedule[Reminder.LUNCH] == time(12, 30)
    assert schedule[Reminder.DINNER] == time(22, 30)


async def log_meals(session, user_id: int, today, at: time, days: int, backfill: bool = False):
    for n in range(1, days + 1):
        day = today - timedelta(days=n)
        logged = day + timedelta(days=1) if backfill else day
        created = datetime.combine(logged, at, MSK)
        session.add(Meal(user_id=user_id, day=day, created_at=created, source="text", title="x"))
    await session.commit()


@pytest.mark.db
async def test_usual_minutes_need_enough_same_day_logs(client):
    await onboarded(client, 1001)
    await onboarded(client, 1002)
    today = utcnow().astimezone(MSK).date()
    async with client.app.state.sessionmaker() as session:
        for uid in (1001, 1002):
            (await session.get(User, uid)).timezone = "Europe/Moscow"
        await log_meals(session, 1001, today, time(12, 10), MIN_DAYS)
        await log_meals(session, 1001, today, time(19, 30), MIN_DAYS - 1)
        await log_meals(session, 1002, today, time(12, 10), MIN_DAYS, backfill=True)
        usual = await usual_meal_minutes(session, [1001, 1002], today)
    assert usual == {1001: {Reminder.LUNCH: 12 * 60 + 10}}


@pytest.mark.db
async def test_lunch_reminder_comes_at_usual_time(client, bot):
    await onboarded(client, 1001)
    today = utcnow().astimezone(MSK).date()
    async with client.app.state.sessionmaker() as session:
        (await session.get(User, 1001)).timezone = "Europe/Moscow"
        await log_meals(session, 1001, today, time(12, 0), MIN_DAYS)

        async def claim(key: str) -> bool:
            return True

        early = datetime.combine(today, time(12, 50), MSK)
        assert await send_due(bot, session, claim, None, early) == 1
    assert [uid for uid, _ in bot.sent] == [1001]
