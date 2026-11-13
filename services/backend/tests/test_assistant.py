from datetime import timedelta

import pytest
from sqlalchemy import update

from belok.db.models import User
from belok.timeutil import utcnow
from tests.conftest import onboarded

pytestmark = pytest.mark.db


async def test_chat_round_trip_with_user_data(client, assistant):
    headers = await onboarded(client)
    await client.post("/api/meals/text", json={"text": "гречка"}, headers=headers)

    r = await client.post(
        "/api/assistant/chats", json={"text": "Сколько белка мне ещё?"}, headers=headers
    )
    assert r.status_code == 201, r.text
    body = r.json()
    chat_id = body["chat"]["id"]
    assert body["chat"]["title"] == "Сколько белка мне ещё?"
    assert [m["role"] for m in body["chat"]["messages"]] == ["user", "assistant"]
    assert body["messages_left"] == 9
    snapshot, history = assistant.calls[0]
    assert "Гречка" in snapshot and "Daily target" in snapshot
    assert history == [{"role": "user", "content": "Сколько белка мне ещё?"}]

    r = await client.post(
        f"/api/assistant/chats/{chat_id}/messages", json={"text": "А завтра?"}, headers=headers
    )
    assert len(r.json()["chat"]["messages"]) == 4
    assert [m["role"] for m in assistant.calls[1][1]] == ["user", "assistant", "user"]

    listing = (await client.get("/api/assistant/chats", headers=headers)).json()
    assert [c["id"] for c in listing["chats"]] == [chat_id]
    assert (listing["messages_left"], listing["daily_messages"]) == (8, 10)
    me = (await client.get("/api/me", headers=headers)).json()
    assert me["analyses_left"] == 2

    other = await onboarded(client, 1002)
    assert (await client.get(f"/api/assistant/chats/{chat_id}", headers=other)).status_code == 404
    assert (
        await client.delete(f"/api/assistant/chats/{chat_id}", headers=headers)
    ).status_code == 204
    assert (await client.get(f"/api/assistant/chats/{chat_id}", headers=headers)).status_code == 404


async def test_chat_needs_premium_and_respects_limits(client, settings, assistant):
    headers = await onboarded(client)
    settings.assistant_trial_messages = 1
    r = await client.post("/api/assistant/chats", json={"text": "привет"}, headers=headers)
    assert r.status_code == 201
    r = await client.post("/api/assistant/chats", json={"text": "ещё"}, headers=headers)
    assert (r.status_code, r.json()["detail"]) == (429, "daily_limit")

    async with client.app.state.sessionmaker() as session:
        await session.execute(
            update(User).where(User.id == 1001).values(trial_ends_at=utcnow() - timedelta(days=1))
        )
        await session.commit()
    r = await client.post("/api/assistant/chats", json={"text": "ещё"}, headers=headers)
    assert (r.status_code, r.json()["detail"]) == (402, "premium_required")
    long = await client.post("/api/assistant/chats", json={"text": "я" * 1001}, headers=headers)
    assert long.status_code == 422


async def test_failed_reply_is_not_counted_and_budget_pauses_chat(client, settings, assistant, bot):
    headers = await onboarded(client)
    settings.admin_id = 1001
    assistant.fail = True
    r = await client.post("/api/assistant/chats", json={"text": "привет"}, headers=headers)
    assert r.status_code == 502
    listing = (await client.get("/api/assistant/chats", headers=headers)).json()
    assert (listing["chats"], listing["messages_left"]) == ([], 10)

    assistant.fail = False
    settings.assistant_daily_budget_usd = 0.0015
    r = await client.post("/api/assistant/chats", json={"text": "привет"}, headers=headers)
    assert r.status_code == 201
    r = await client.post("/api/assistant/chats", json={"text": "ещё"}, headers=headers)
    assert r.status_code == 201
    assert any("дневной лимит" in text for _, text in bot.sent)
    r = await client.post("/api/assistant/chats", json={"text": "и ещё"}, headers=headers)
    assert (r.status_code, r.json()["detail"]) == (503, "assistant_busy")
