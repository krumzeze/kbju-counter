import asyncio
from datetime import datetime, timedelta

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.methods import SendMessage
from sqlalchemy import select, update

from belok.db.models import Broadcast, User
from belok.services import broadcasts
from belok.services.referrals import reward_for_payment
from belok.timeutil import utcnow
from tests.conftest import login, onboarded
from tests.telegram_signing import sign_init_data

pytestmark = pytest.mark.db

ADMIN, USER, OTHER = 1001, 2002, 3003


async def admin_and_user(client):
    admin = await onboarded(client, ADMIN)
    user = await onboarded(client, USER)
    return admin, user


async def test_first_user_becomes_admin(client):
    admin, user = await admin_and_user(client)
    assert (await client.get("/api/me", headers=admin)).json()["is_admin"] is True
    assert (await client.get("/api/me", headers=user)).json()["is_admin"] is False


async def test_admin_id_setting_overrides_first_user(client, settings):
    settings.admin_id = USER
    first = await login(client, ADMIN)
    second = await login(client, USER)
    assert (await client.get("/api/me", headers=first)).json()["is_admin"] is False
    assert (await client.get("/api/me", headers=second)).json()["is_admin"] is True


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/admin/dashboard"),
        ("get", "/api/admin/users"),
        ("get", f"/api/admin/users/{ADMIN}"),
        ("patch", f"/api/admin/users/{USER}"),
        ("post", f"/api/admin/users/{USER}/grant"),
        ("post", f"/api/admin/users/{USER}/revoke"),
        ("post", f"/api/admin/users/{USER}/message"),
        ("delete", f"/api/admin/users/{ADMIN}"),
        ("get", "/api/admin/promos"),
        ("post", "/api/admin/promos"),
        ("patch", "/api/admin/promos/1"),
        ("get", "/api/admin/segments"),
        ("get", "/api/admin/broadcasts"),
        ("post", "/api/admin/broadcasts"),
        ("post", "/api/admin/broadcasts/1/send"),
        ("post", "/api/admin/broadcasts/1/cancel"),
        ("get", "/api/admin/referrals"),
        ("get", "/api/admin/actions"),
        ("get", "/api/admin/prefs"),
        ("put", "/api/admin/prefs"),
    ],
)
async def test_admin_endpoints_reject_regular_users(client, method, path):
    _, user = await admin_and_user(client)
    kwargs = {} if method in {"get", "delete"} else {"json": {}}
    response = await getattr(client, method)(path, headers=user, **kwargs)
    assert response.status_code == 403
    assert response.json()["detail"] == "admin_only"


async def test_new_user_notifies_admin(client, bot):
    await login(client, ADMIN)
    await login(client, USER)
    assert [chat for chat, _ in bot.sent] == [ADMIN]


async def test_dashboard(client):
    admin, user = await admin_and_user(client)
    await client.post("/api/meals/text", json={"text": "гречка"}, headers=user)
    await client.put("/api/steps/today", json={"steps": 9000}, headers=admin)

    d = (await client.get("/api/admin/dashboard", headers=admin)).json()
    assert d["users_total"] == 2
    assert d["new_today"] == 2
    assert d["dau"] == 2
    assert d["statuses"]["trial"] == 2
    assert d["cost_today"] == pytest.approx(0.001)
    assert d["requests_24h"] == 1
    assert d["error_rate_24h"] == 0
    assert dict((f["key"], f["count"]) for f in d["funnel"]) == {
        "registered": 2,
        "profile": 2,
        "first_meal": 1,
        "active_3_days": 0,
    }
    assert d["sources"] == [{"key": "direct", "count": 2}]
    assert len(d["series"]) == 30
    assert d["series"][-1]["new_users"] == 2
    assert d["series"][-1]["active_users"] == 2


async def test_user_list_search_filter_and_sort(client):
    admin, user = await admin_and_user(client)
    await client.post("/api/meals/text", json={"text": "гречка"}, headers=user)
    await onboarded(client, OTHER)

    page = (await client.get("/api/admin/users?sort=analyses", headers=admin)).json()
    assert page["total"] == 3
    assert page["items"][0]["id"] == USER
    assert page["items"][0]["analyses"] == 1

    found = (await client.get(f"/api/admin/users?q={OTHER}", headers=admin)).json()
    assert [u["id"] for u in found["items"]] == [OTHER]
    assert (await client.get("/api/admin/users?q=%25", headers=admin)).json()["total"] == 0

    admins = (await client.get("/api/admin/users?filter=admins", headers=admin)).json()
    assert [u["id"] for u in admins["items"]] == [ADMIN]


async def test_user_detail(client):
    admin, user = await admin_and_user(client)
    await client.post("/api/meals/text", json={"text": "гречка"}, headers=user)
    detail = (await client.get(f"/api/admin/users/{USER}", headers=admin)).json()
    assert detail["status"] == "trial"
    assert detail["weight_kg"] == 80
    assert len(detail["activity"]) == 30
    assert detail["activity"][-1]["meals"] == 1
    assert detail["meals"][0]["title"] == "Обед"
    assert detail["llm"][0]["ok"] is True
    assert (await client.get("/api/admin/users/999", headers=admin)).status_code == 404


async def test_grant_revoke_and_lifetime(client):
    admin, user = await admin_and_user(client)
    before = (await client.get("/api/me", headers=user)).json()["access_until"]

    granted = (
        await client.post(f"/api/admin/users/{USER}/grant", json={"days": 30}, headers=admin)
    ).json()
    assert granted["status"] == "active"
    assert granted["access_until"] > before

    revoked = (await client.post(f"/api/admin/users/{USER}/revoke", headers=admin)).json()
    assert revoked["status"] == "expired"
    assert (await client.get("/api/day", headers=user)).status_code == 402

    lifetime = await client.patch(
        f"/api/admin/users/{USER}", json={"lifetime_access": True}, headers=admin
    )
    assert lifetime.json()["status"] == "lifetime"
    assert (await client.get("/api/day", headers=user)).status_code == 200

    log = (await client.get("/api/admin/actions", headers=admin)).json()
    assert [a["action"] for a in log] == ["set_lifetime_access", "revoke_access", "grant_days"]
    assert log[0]["target"]["id"] == USER


async def test_block_user(client):
    admin, user = await admin_and_user(client)
    await client.patch(f"/api/admin/users/{USER}", json={"is_blocked": True}, headers=admin)
    assert (await client.get("/api/me", headers=user)).status_code == 403
    relogin = await client.post("/api/auth/webapp", json={"init_data": sign_init_data(USER)})
    assert relogin.status_code == 403


async def test_admin_cannot_lock_themselves_out(client):
    admin, _ = await admin_and_user(client)
    for body in ({"is_blocked": True}, {"is_admin": False}):
        response = await client.patch(f"/api/admin/users/{ADMIN}", json=body, headers=admin)
        assert response.status_code == 400
    assert (await client.delete(f"/api/admin/users/{ADMIN}", headers=admin)).status_code == 400


async def test_promoted_admin_cannot_be_blocked(client):
    admin, user = await admin_and_user(client)
    await client.patch(f"/api/admin/users/{USER}", json={"is_admin": True}, headers=admin)
    response = await client.patch(
        f"/api/admin/users/{USER}", json={"is_blocked": True}, headers=admin
    )
    assert response.status_code == 400
    assert (await client.get("/api/admin/dashboard", headers=user)).status_code == 200


async def test_daily_limit_override(client):
    admin, user = await admin_and_user(client)
    await client.patch(f"/api/admin/users/{USER}", json={"daily_limit": 1}, headers=admin)
    first = await client.post("/api/meals/text", json={"text": "гречка"}, headers=user)
    second = await client.post("/api/meals/text", json={"text": "гречка"}, headers=user)
    assert (first.status_code, second.status_code) == (201, 429)


async def test_message_and_delete_user(client, bot):
    admin, user = await admin_and_user(client)
    bot.sent.clear()
    response = await client.post(
        f"/api/admin/users/{USER}/message", json={"text": "Привет"}, headers=admin
    )
    assert response.status_code == 204
    assert bot.sent == [(USER, "Привет")]

    bot.fail_for[USER] = TelegramBadRequest(SendMessage(chat_id=USER, text="x"), "can't parse")
    response = await client.post(
        f"/api/admin/users/{USER}/message", json={"text": "<b>"}, headers=admin
    )
    assert response.status_code == 400

    await client.post("/api/meals/text", json={"text": "гречка"}, headers=user)
    assert (await client.delete(f"/api/admin/users/{USER}", headers=admin)).status_code == 204
    assert (await client.get(f"/api/admin/users/{USER}", headers=admin)).status_code == 404
    assert (await client.get("/api/me", headers=user)).status_code == 401


async def test_promo_redeem(client):
    admin, user = await admin_and_user(client)
    created = await client.post(
        "/api/admin/promos", json={"code": " belok-10 ", "days": 10}, headers=admin
    )
    assert created.status_code == 201
    assert created.json()["code"] == "BELOK-10"
    duplicate = await client.post(
        "/api/admin/promos", json={"code": "BELOK-10", "days": 1}, headers=admin
    )
    assert duplicate.status_code == 409

    ok = await client.post("/api/me/promo", json={"code": "belok-10"}, headers=user)
    assert ok.status_code == 200
    assert ok.json()["days"] == 10
    me = (await client.get("/api/me", headers=user)).json()
    assert me["status"] == "active"

    again = await client.post("/api/me/promo", json={"code": "BELOK-10"}, headers=user)
    assert again.json()["detail"] == "already_used"

    promos = (await client.get("/api/admin/promos", headers=admin)).json()
    assert promos[0]["activations"] == 1


async def test_generated_promo_code(client):
    admin, _ = await admin_and_user(client)
    promo = (await client.post("/api/admin/promos", json={"days": 3}, headers=admin)).json()
    assert len(promo["code"]) == 10
    assert not set(promo["code"]) & set("01IO")


async def test_promo_activation_limit_holds_under_concurrency(client):
    admin = await onboarded(client, ADMIN)
    await client.post(
        "/api/admin/promos", json={"code": "ONE", "days": 5, "max_activations": 1}, headers=admin
    )
    users = [await login(client, 5000 + i) for i in range(6)]
    responses = await asyncio.gather(
        *(client.post("/api/me/promo", json={"code": "ONE"}, headers=h) for h in users)
    )
    codes = sorted(r.status_code for r in responses)
    assert codes == [200, 400, 400, 400, 400, 400]
    assert {r.json()["detail"] for r in responses if r.status_code == 400} == {"exhausted"}
    promos = (await client.get("/api/admin/promos", headers=admin)).json()
    assert promos[0]["activations"] == 1


async def test_same_user_double_submit_redeems_once(client):
    admin, user = await admin_and_user(client)
    await client.post("/api/admin/promos", json={"code": "TWICE", "days": 5}, headers=admin)
    responses = await asyncio.gather(
        *(client.post("/api/me/promo", json={"code": "TWICE"}, headers=user) for _ in range(5))
    )
    assert sorted(r.status_code for r in responses) == [200, 400, 400, 400, 400]
    promos = (await client.get("/api/admin/promos", headers=admin)).json()
    assert promos[0]["activations"] == 1


async def test_promo_guessing_is_rate_limited(client):
    admin, user = await admin_and_user(client)
    await client.post("/api/admin/promos", json={"code": "REAL", "days": 5}, headers=admin)
    for attempt in range(5):
        response = await client.post("/api/me/promo", json={"code": f"FAKE{attempt}"}, headers=user)
        assert response.json()["detail"] == "not_found"
    blocked = await client.post("/api/me/promo", json={"code": "REAL"}, headers=user)
    assert blocked.status_code == 429


async def test_promo_restrictions(client):
    admin, user = await admin_and_user(client)
    past = (utcnow() - timedelta(days=1)).isoformat()
    await client.post(
        "/api/admin/promos", json={"code": "OLD", "days": 5, "expires_at": past}, headers=admin
    )
    await client.post(
        "/api/admin/promos",
        json={"code": "NEWBIE", "days": 5, "new_users_only": True},
        headers=admin,
    )
    off = (
        await client.post("/api/admin/promos", json={"code": "OFF", "days": 5}, headers=admin)
    ).json()
    await client.patch(f"/api/admin/promos/{off['id']}", json={"active": False}, headers=admin)

    async def redeem(code):
        return (await client.post("/api/me/promo", json={"code": code}, headers=user)).json()

    assert (await redeem("OLD"))["detail"] == "expired"
    assert (await redeem("OFF"))["detail"] == "not_found"
    async with client.app.state.sessionmaker() as session:
        await session.execute(
            update(User).where(User.id == USER).values(created_at=utcnow() - timedelta(days=30))
        )
        await session.commit()
    assert (await redeem("NEWBIE"))["detail"] == "new_users_only"


async def test_referral_attribution_and_rewards(client, settings):
    settings.bot_username = "belok_bot"
    admin = await onboarded(client, ADMIN)
    link = (await client.get("/api/me/referral", headers=admin)).json()["link"]
    ref_code = link.removeprefix("https://t.me/belok_bot?start=r_")

    friend = await login(client, USER, start_param=f"r_{ref_code}")
    me = (await client.get("/api/me", headers=friend)).json()
    assert (datetime.fromisoformat(me["trial_ends_at"]) - utcnow()).days == 6

    stranger = await login(client, OTHER, start_param="r_NOSUCHCODE")
    assert (await client.get("/api/me", headers=stranger)).status_code == 200

    async with client.app.state.sessionmaker() as session:
        payer = await session.get(User, USER)
        assert payer.referred_by_id == ADMIN
        assert (await session.get(User, OTHER)).referred_by_id is None
        assert await reward_for_payment(session, payer, "pay-1", 7) is not None
        assert await reward_for_payment(session, payer, "pay-1", 7) is None
        await session.commit()

    stats = (await client.get("/api/me/referral", headers=admin)).json()
    assert (stats["invited"], stats["paid"], stats["days"]) == (1, 1, 7)
    sources = (await client.get("/api/admin/dashboard", headers=admin)).json()["sources"]
    assert {s["key"]: s["count"] for s in sources} == {
        "direct": 1,
        "referral": 1,
        "r_NOSUCHCODE": 1,
    }
    top = (await client.get("/api/admin/referrals", headers=admin)).json()
    assert top[0]["id"] == ADMIN and top[0]["invited"] == 1


async def test_existing_user_cannot_be_reattributed(client):
    admin = await onboarded(client, ADMIN)
    await login(client, USER)
    async with client.app.state.sessionmaker() as session:
        ref_code = (await session.get(User, ADMIN)).referral_code
    await login(client, USER, start_param=f"r_{ref_code}")
    async with client.app.state.sessionmaker() as session:
        assert (await session.get(User, USER)).referred_by_id is None
    assert (await client.get("/api/me/referral", headers=admin)).json()["invited"] == 0


async def test_broadcast_flow(client, bot):
    admin, _ = await admin_and_user(client)
    await onboarded(client, OTHER)
    bot.sent.clear()

    draft = await client.post(
        "/api/admin/broadcasts", json={"text": "Новости", "segment": "all"}, headers=admin
    )
    assert draft.status_code == 201
    assert bot.sent == [(ADMIN, "Новости")]
    broadcast_id = draft.json()["id"]

    sending = await client.post(f"/api/admin/broadcasts/{broadcast_id}/send", headers=admin)
    assert sending.json()["status"] == "sending"
    assert sending.json()["total"] == 3
    again = await client.post(f"/api/admin/broadcasts/{broadcast_id}/send", headers=admin)
    assert again.status_code == 409

    bot.sent.clear()
    bot.fail_for[OTHER] = TelegramForbiddenError(SendMessage(chat_id=OTHER, text="x"), "blocked")
    sessionmaker = client.app.state.sessionmaker
    broadcasts.BATCH_INTERVAL = 0
    while await broadcasts._step(bot, sessionmaker):
        async with sessionmaker() as session:
            status = await session.scalar(
                select(Broadcast.status).where(Broadcast.id == broadcast_id)
            )
        if status == "done":
            break

    result = (await client.get("/api/admin/broadcasts", headers=admin)).json()[0]
    assert (result["status"], result["sent"], result["blocked"]) == ("done", 2, 1)
    assert sorted(chat for chat, _ in bot.sent) == [ADMIN, USER]
    async with sessionmaker() as session:
        assert (await session.get(User, OTHER)).bot_blocked is True
    segments = (await client.get("/api/admin/segments", headers=admin)).json()
    assert dict((s["key"], s["count"]) for s in segments)["all"] == 2


async def test_cancel_broadcast(client):
    admin, _ = await admin_and_user(client)
    draft = (
        await client.post(
            "/api/admin/broadcasts", json={"text": "x", "segment": "trial"}, headers=admin
        )
    ).json()
    cancelled = await client.post(f"/api/admin/broadcasts/{draft['id']}/cancel", headers=admin)
    assert cancelled.json()["status"] == "cancelled"
    assert (
        await client.post(f"/api/admin/broadcasts/{draft['id']}/send", headers=admin)
    ).status_code == 409


async def test_prefs(client):
    admin, _ = await admin_and_user(client)
    assert (await client.get("/api/admin/prefs", headers=admin)).json() == {
        "new_users": True,
        "errors": True,
        "daily": True,
    }
    updated = await client.put("/api/admin/prefs", json={"daily": False}, headers=admin)
    assert updated.json() == {"new_users": True, "errors": True, "daily": False}
