import io
from datetime import timedelta

import pytest
from PIL import Image
from sqlalchemy import update

from belok.db.models import LlmUsage, User
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


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 120, 40)).save(out, "PNG")
    return out.getvalue()


async def test_menu_photo_suggests_dishes_that_can_be_logged(client, assistant):
    headers = await onboarded(client)
    r = await client.post(
        "/api/assistant/photo",
        data={"mode": "menu", "note": "ужин"},
        files={"photo": ("menu.png", png(), "image/png")},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    chat = r.json()["chat"]
    assert chat["title"] == "📷 Фото меню: ужин"
    user_msg, answer = chat["messages"]
    assert (user_msg["text"], user_msg["data"]) == ("📷 Фото меню: ужин", {"photo": "menu"})
    assert answer["text"] == "Бери лосося"
    assert [d["name"] for d in answer["data"]["dishes"]] == ["Стейк из лосося", "Паста карбонара"]
    assert assistant.calls[0][1] == [{"mode": "menu", "note": "ужин", "media_type": "image/png"}]

    r = await client.post(f"/api/assistant/messages/{answer['id']}/dishes/0", headers=headers)
    assert r.status_code == 201, r.text
    assert r.json()["message"]["data"]["logged"] == [0]
    assert (r.json()["meal"]["source"], r.json()["meal"]["totals"]["kcal"]) == ("ai", 420)
    day = (await client.get("/api/day", headers=headers)).json()
    assert [m["title"] for m in day["meals"]] == ["Стейк из лосося"]

    missing = await client.post(f"/api/assistant/messages/{answer['id']}/dishes/5", headers=headers)
    assert missing.status_code == 404
    other = await onboarded(client, 1002)
    r = await client.post(f"/api/assistant/messages/{answer['id']}/dishes/1", headers=other)
    assert r.status_code == 404

    r = await client.post(
        f"/api/assistant/chats/{chat['id']}/photo",
        data={"mode": "fridge"},
        files={"photo": ("fridge.png", png(), "image/png")},
        headers=headers,
    )
    assert len(r.json()["chat"]["messages"]) == 4
    assert r.json()["messages_left"] == 8


async def test_photo_limit_per_day(client, settings, assistant):
    headers = await onboarded(client)
    settings.assistant_trial_messages = 20
    for _ in range(5):
        r = await client.post(
            "/api/assistant/photo",
            data={"mode": "fridge"},
            files={"photo": ("f.png", png(), "image/png")},
            headers=headers,
        )
        assert r.status_code == 201
        async with client.app.state.sessionmaker() as session:
            await session.execute(
                update(LlmUsage).values(created_at=utcnow() - timedelta(minutes=2))
            )
            await session.commit()
    r = await client.post(
        "/api/assistant/photo",
        data={"mode": "fridge"},
        files={"photo": ("f.png", png(), "image/png")},
        headers=headers,
    )
    assert (r.status_code, r.json()["detail"]) == (429, "photo_limit")
    bad = await client.post(
        "/api/assistant/photo",
        data={"mode": "garage"},
        files={"photo": ("f.png", png(), "image/png")},
        headers=headers,
    )
    assert bad.status_code == 422
