from datetime import datetime, time, timedelta

import pytest
from sqlalchemy import select, update

from belok.db.models import AiChat, Meal, MealItem, User
from belok.services.reviews import write_due
from belok.timeutil import utcnow
from tests.conftest import FakeBot, onboarded

pytestmark = pytest.mark.db


def next_monday_morning() -> datetime:
    now = utcnow()
    monday = now.date() + timedelta(days=7 - now.weekday())
    return datetime.combine(monday, time(10, 30), now.tzinfo)


async def log_days(session, user_id: int, monday, days: int) -> None:
    for i in range(days):
        item = MealItem(name="Гречка", grams=200, kcal=220, protein=8, fat=2, carbs=42)
        session.add(
            Meal(
                user_id=user_id,
                day=monday - timedelta(days=i + 1),
                source="text",
                title="Обед",
                items=[item],
            )
        )


async def test_weekly_review_written_once_for_active_users(client, settings, assistant):
    await onboarded(client)
    await onboarded(client, 1002)
    now = next_monday_morning()
    bot = FakeBot()
    async with client.app.state.sessionmaker() as session:
        await session.execute(update(User).values(last_seen_at=now))
        await log_days(session, 1001, now.date(), 3)
        await log_days(session, 1002, now.date(), 2)
        await session.commit()

        early = now.replace(hour=9)
        assert await write_due(bot, session, assistant, settings, early) == 0
        assert await write_due(bot, session, assistant, settings, now) == 1
        assert await write_due(bot, session, assistant, settings, now) == 0

    async with client.app.state.sessionmaker() as session:
        chats = list(await session.scalars(select(AiChat)))
    assert [(c.user_id, c.kind) for c in chats] == [(1001, "review")]
    assert chats[0].title.startswith("Разбор недели")
    assert [(chat, "Разбор недели" in text) for chat, text in bot.sent] == [(1001, True)]
    snapshot, _ = assistant.calls[0]
    assert "Гречка" not in snapshot.split("Previous 7 days")[0]

    headers = await onboarded(client)
    listing = (await client.get("/api/assistant/chats", headers=headers)).json()
    assert [c["kind"] for c in listing["chats"]] == ["review"]


async def test_no_review_without_premium(client, settings, assistant):
    await onboarded(client)
    now = next_monday_morning()
    async with client.app.state.sessionmaker() as session:
        await session.execute(
            update(User).values(last_seen_at=now, trial_ends_at=now - timedelta(days=1))
        )
        await log_days(session, 1001, now.date(), 5)
        await session.commit()
        assert await write_due(FakeBot(), session, assistant, settings, now) == 0
