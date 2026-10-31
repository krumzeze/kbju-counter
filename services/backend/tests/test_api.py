from datetime import timedelta

import pytest
from sqlalchemy import update

from belok.db.models import User
from belok.timeutil import utcnow
from tests.conftest import PROFILE, login, onboarded
from tests.telegram_signing import sign_widget

pytestmark = pytest.mark.db


async def test_requests_without_token_are_rejected(client):
    assert (await client.get("/api/me")).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert (await client.get("/api/me", headers=bad)).status_code == 401


async def test_invalid_init_data_is_rejected(client):
    response = await client.post("/api/auth/webapp", json={"init_data": "user=1&hash=00"})
    assert response.status_code == 401


async def test_widget_login_creates_same_user(client):
    response = await client.post("/api/auth/widget", json=sign_widget(1001))
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['token']}"}
    assert (await client.get("/api/me", headers=headers)).json()["id"] == 1001


async def test_new_user_gets_trial_and_needs_profile(client):
    headers = await login(client)
    me = (await client.get("/api/me", headers=headers)).json()
    assert me["profile_complete"] is False
    assert me["has_access"] is True
    assert (await client.get("/api/day", headers=headers)).status_code == 409


async def test_profile_sets_base_target(client):
    headers = await login(client)
    response = await client.put(
        "/api/me/profile", json=PROFILE | {"timezone": "Asia/Dushanbe"}, headers=headers
    )
    me = response.json()
    assert me["profile_complete"] is True
    assert me["age"] == 30
    assert me["weight_kg"] == 80
    assert me["timezone"] == "Asia/Dushanbe"
    assert me["base_target"]["kcal"] == pytest.approx(1780 * 1.2)


async def test_language_starts_unset_and_can_be_chosen(client):
    headers = await login(client)
    assert (await client.get("/api/me", headers=headers)).json()["language"] is None
    response = await client.put("/api/me/language", json={"language": "en"}, headers=headers)
    assert response.json()["language"] == "en"
    bad = await client.put("/api/me/language", json={"language": "de"}, headers=headers)
    assert bad.status_code == 422


async def test_invalid_timezone_is_rejected(client):
    headers = await login(client)
    response = await client.put(
        "/api/me/profile", json=PROFILE | {"timezone": "Mars/Base"}, headers=headers
    )
    assert response.status_code == 422


async def test_meal_lifecycle(client):
    headers = await onboarded(client)

    created = await client.post("/api/meals/text", json={"text": "гречка"}, headers=headers)
    assert created.status_code == 201
    meal = created.json()
    assert meal["totals"]["kcal"] == 220

    patched = await client.patch(f"/api/meals/{meal['id']}", json={"scale": 1.5}, headers=headers)
    assert patched.json()["totals"]["kcal"] == pytest.approx(330)

    day = (await client.get("/api/day", headers=headers)).json()
    assert [m["id"] for m in day["meals"]] == [meal["id"]]
    assert day["eaten"]["kcal"] == pytest.approx(330)

    assert (await client.delete(f"/api/meals/{meal['id']}", headers=headers)).status_code == 204
    day = (await client.get("/api/day", headers=headers)).json()
    assert day["meals"] == []


async def test_photo_meal(client):
    headers = await onboarded(client)
    response = await client.post(
        "/api/meals/photo",
        files={"photo": ("food.jpg", b"\xff\xd8fake", "image/jpeg")},
        data={"note": "200 г"},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["source"] == "photo"


async def test_photo_with_wrong_type_is_rejected(client):
    headers = await onboarded(client)
    response = await client.post(
        "/api/meals/photo", files={"photo": ("a.gif", b"GIF89a", "image/gif")}, headers=headers
    )
    assert response.status_code == 415


async def test_no_food_returns_422(client, analyzer):
    analyzer.items = []
    headers = await onboarded(client)
    response = await client.post("/api/meals/text", json={"text": "стол"}, headers=headers)
    assert response.status_code == 422


async def test_daily_limit(client):
    headers = await onboarded(client)
    for _ in range(3):
        r = await client.post("/api/meals/text", json={"text": "еда"}, headers=headers)
        assert r.status_code == 201
    r = await client.post("/api/meals/text", json={"text": "еда"}, headers=headers)
    assert r.status_code == 429


async def test_users_cannot_touch_each_others_meals(client):
    alice = await onboarded(client, 1)
    bob = await onboarded(client, 2)
    meal = (await client.post("/api/meals/text", json={"text": "еда"}, headers=alice)).json()
    assert (await client.delete(f"/api/meals/{meal['id']}", headers=bob)).status_code == 404
    assert (await client.get("/api/day", headers=bob)).json()["meals"] == []


async def test_steps_raise_daily_target_by_weekly_average(client):
    headers = await onboarded(client)
    before = (await client.get("/api/day", headers=headers)).json()["target"]["kcal"]
    assert (
        await client.put("/api/steps/today", json={"steps": 13000}, headers=headers)
    ).status_code == 204
    day = (await client.get("/api/day", headers=headers)).json()
    assert day["steps"] == 13000
    assert day["activity_kcal"] == pytest.approx(400 / 7)
    assert day["target"]["kcal"] == pytest.approx(before + 400 / 7)


async def test_weights(client):
    headers = await onboarded(client)
    await client.put("/api/weights/today", json={"weight_kg": 79.4}, headers=headers)
    weights = (await client.get("/api/weights", headers=headers)).json()
    assert [w["weight_kg"] for w in weights] == [79.4]


async def test_expired_trial_blocks_data_but_not_profile(client):
    headers = await onboarded(client)
    async with client.app.state.sessionmaker() as session:
        await session.execute(
            update(User).where(User.id == 1001).values(trial_ends_at=utcnow() - timedelta(days=1))
        )
        await session.commit()
    assert (await client.get("/api/day", headers=headers)).status_code == 402
    me = (await client.get("/api/me", headers=headers)).json()
    assert me["has_access"] is False
