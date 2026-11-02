import pytest

from belok.db.models import User
from belok.services import support
from tests.conftest import onboarded

pytestmark = pytest.mark.db

ADMIN, USER = 1001, 2002


async def test_message_reaches_admin_and_reply_reaches_user(client, bot):
    await onboarded(client, ADMIN)
    user = await onboarded(client, USER)

    response = await client.post("/api/support", json={"text": "не прошла оплата"}, headers=user)
    assert response.status_code == 201
    admin_chat, card = bot.sent[-1]
    assert admin_chat == ADMIN and "не прошла оплата" in card and str(USER) in card
    relayed_id = len(bot.sent)

    async with client.app.state.sessionmaker() as session:
        admin = await session.get(User, ADMIN)
        target = await support.reply(session, bot, admin, ADMIN, relayed_id, "уже проверяем")
        assert target.id == USER
        assert await support.reply(session, bot, admin, ADMIN, 999, "мимо") is None
    assert bot.sent[-1][0] == USER and "уже проверяем" in bot.sent[-1][1]

    thread = (await client.get("/api/support", headers=user)).json()
    assert [(m["from_admin"], m["text"]) for m in thread] == [
        (False, "не прошла оплата"),
        (True, "уже проверяем"),
    ]


async def test_support_rejects_blank_and_limits_spam(client, monkeypatch):
    user = await onboarded(client, USER)
    blank = await client.post("/api/support", json={"text": "   "}, headers=user)
    assert blank.status_code == 422
    monkeypatch.setattr(support, "DAILY_LIMIT", 1)
    first = await client.post("/api/support", json={"text": "раз"}, headers=user)
    second = await client.post("/api/support", json={"text": "два"}, headers=user)
    assert (first.status_code, second.status_code) == (201, 429)
