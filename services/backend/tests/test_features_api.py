from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import select, update

from belok.db.models import BodyWeight, Meal, MealItem, User
from belok.services.products import ProductInfo
from belok.services.reminders import send_due
from belok.timeutil import utcnow
from tests.conftest import onboarded
from tests.test_products import barcode_png

pytestmark = pytest.mark.db


async def seed_history(client, kcal: float = 2300, days: int = 20, loss_kg: float = 0.6) -> None:
    today = utcnow().date()
    async with client.app.state.sessionmaker() as session:
        for i in range(1, days + 1):
            item = MealItem(name="Еда", grams=500, kcal=kcal, protein=100, fat=80, carbs=250)
            session.add(
                Meal(
                    user_id=1001,
                    day=today - timedelta(days=i),
                    source="text",
                    title="День",
                    scale=1.0,
                    items=[item],
                )
            )
        for i in range(8):
            day = today - timedelta(days=24 - i * 3)
            session.add(BodyWeight(user_id=1001, day=day, weight_kg=81 - loss_kg * i / 7))
        await session.commit()


async def test_adaptive_target_requires_enough_data(client):
    headers = await onboarded(client)
    me = (await client.get("/api/me", headers=headers)).json()
    assert me["adaptive"]["ready"] is False
    assert me["adaptive"]["logged_days"] == 0
    response = await client.patch(
        "/api/me/settings", json={"adaptive_target": True}, headers=headers
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "adaptive_not_ready"


async def test_adaptive_target_uses_measured_expenditure(client):
    headers = await onboarded(client)
    await seed_history(client)
    me = (await client.get("/api/me", headers=headers)).json()
    assert me["adaptive"]["ready"] is True
    tdee = me["adaptive"]["tdee"]
    assert tdee > 2300

    me = (
        await client.patch("/api/me/settings", json={"adaptive_target": True}, headers=headers)
    ).json()
    assert me["adaptive_target"] is True
    day = (await client.get("/api/day", headers=headers)).json()
    assert day["target_source"] == "adaptive"
    assert day["adaptive_paused"] is False
    assert day["activity_kcal"] == 0
    assert day["target"]["kcal"] == pytest.approx(tdee)


async def test_adaptive_target_falls_back_when_data_runs_out(client):
    headers = await onboarded(client)
    await seed_history(client)
    await client.patch("/api/me/settings", json={"adaptive_target": True}, headers=headers)
    async with client.app.state.sessionmaker() as session:
        await session.execute(update(Meal).values(day=utcnow().date() - timedelta(days=60)))
        await session.commit()
    day = (await client.get("/api/day", headers=headers)).json()
    assert day["target_source"] == "formula"
    assert day["adaptive_paused"] is True


async def test_settings_toggle_reminders(client):
    headers = await onboarded(client)
    me = (await client.get("/api/me", headers=headers)).json()
    assert me["remind_meals"] is True and me["remind_weight"] is True
    me = (
        await client.patch("/api/me/settings", json={"remind_meals": False}, headers=headers)
    ).json()
    assert me["remind_meals"] is False and me["remind_weight"] is True


async def test_water_is_added_and_clamped(client):
    headers = await onboarded(client)
    day = (await client.get("/api/day", headers=headers)).json()
    assert day["water_ml"] == 0
    assert day["water_target_ml"] == 2400
    r = await client.post("/api/water/today", json={"delta_ml": 250}, headers=headers)
    assert r.json() == {"water_ml": 250}
    r = await client.post("/api/water/today", json={"delta_ml": -500}, headers=headers)
    assert r.json() == {"water_ml": 0}
    await client.put("/api/steps/today", json={"steps": 5000}, headers=headers)
    await client.post("/api/water/today", json={"delta_ml": 500}, headers=headers)
    day = (await client.get("/api/day", headers=headers)).json()
    assert (day["steps"], day["water_ml"]) == (5000, 500)


async def test_steps_and_water_for_past_days(client):
    headers = await onboarded(client)
    today = datetime.fromisoformat(
        (await client.get("/api/day", headers=headers)).json()["day"]
    ).date()
    yesterday = (today - timedelta(days=1)).isoformat()
    r = await client.put(f"/api/steps/today?day={yesterday}", json={"steps": 7000}, headers=headers)
    assert r.status_code == 204
    r = await client.post(
        f"/api/water/today?day={yesterday}", json={"delta_ml": 300}, headers=headers
    )
    assert r.json() == {"water_ml": 300}
    day = (await client.get(f"/api/day?day={yesterday}", headers=headers)).json()
    assert (day["steps"], day["water_ml"]) == (7000, 300)
    for bad in (today + timedelta(days=1), today - timedelta(days=7)):
        r = await client.put(f"/api/steps/today?day={bad}", json={"steps": 1}, headers=headers)
        assert r.status_code == 422


async def test_barcode_lookup_is_cached(client, food_db):
    headers = await onboarded(client)
    await client.put("/api/me/language", json={"language": "ru"}, headers=headers)
    food_db.products["4600000000008"] = ProductInfo("Кефир", 53, 2.9, 2.5, 4, 250)
    for _ in range(2):
        r = await client.get("/api/barcode/4600000000008", headers=headers)
        assert r.status_code == 200
        assert r.json()["product"]["name"] == "Кефир"
    assert food_db.lookups == ["4600000000008"]

    r = await client.get("/api/barcode/4601111111118", headers=headers)
    assert r.json() == {"code": "4601111111118", "product": None}
    assert (await client.get("/api/barcode/abc", headers=headers)).status_code == 422


async def test_barcode_from_photo(client, food_db):
    headers = await onboarded(client)
    food_db.products["4600000000008"] = ProductInfo("Кефир", 53, 2.9, 2.5, 4, None)
    files = {"photo": ("code.png", barcode_png("4600000000008"), "image/png")}
    r = await client.post("/api/barcode/photo", files=files, headers=headers)
    assert r.status_code == 200
    assert r.json()["code"] == "4600000000008"

    blank = {"photo": ("x.png", barcode_png("4600000000008")[:50], "image/png")}
    r = await client.post("/api/barcode/photo", files=blank, headers=headers)
    assert r.json()["detail"] == "no_barcode"


async def test_manual_meal_with_barcode_is_remembered(client, food_db):
    headers = await onboarded(client)
    body = {
        "title": "Сырок",
        "grams": 40,
        "kcal": 400,
        "protein": 8,
        "fat": 25,
        "carbs": 30,
        "barcode": "4602222222225",
    }
    meal = (await client.post("/api/meals/manual", json=body, headers=headers)).json()
    assert meal["source"] == "barcode"
    product = (await client.get("/api/barcode/4602222222225", headers=headers)).json()["product"]
    assert product["name"] == "Сырок"
    assert product["serving_g"] == 40
    assert food_db.lookups == []


async def test_stats_sum_each_day(client):
    headers = await onboarded(client)
    body = {"title": "Rice", "grams": 200, "kcal": 130, "protein": 2.5, "fat": 0.5, "carbs": 28}
    await client.post("/api/meals/manual", json=body, headers=headers)
    await client.post("/api/meals/manual", json=body, headers=headers)
    await client.put("/api/steps/today", json={"steps": 4000}, headers=headers)

    stats = (await client.get("/api/stats?days=7", headers=headers)).json()
    assert len(stats["days"]) == 7
    today = stats["days"][-1]
    assert today["eaten"]["kcal"] == 520
    assert (today["steps"], today["water_ml"], today["sets"]) == (4000, 0, 0)
    assert stats["days"][0]["eaten"]["kcal"] == 0
    assert stats["target"]["kcal"] > 0
    assert stats["water_target_ml"] == 2400
    assert stats["limited"] is False
    assert (await client.get("/api/stats?days=0", headers=headers)).status_code == 422


def at(hour: int, minute: int = 0) -> datetime:
    return datetime.combine(utcnow().date(), time(hour, minute), UTC)


async def reminders(client, bot, now: datetime, claimed: set[str]) -> int:
    async def claim(key: str) -> bool:
        if key in claimed:
            return False
        claimed.add(key)
        return True

    async with client.app.state.sessionmaker() as session:
        return await send_due(bot, session, claim, "https://app.test", now)


async def test_lunch_reminder_once_when_nothing_logged(client, bot):
    await onboarded(client)
    claimed: set[str] = set()
    assert await reminders(client, bot, at(14, 10), claimed) == 1
    assert "ещё нет ни одной записи" in bot.sent[0][1]
    assert await reminders(client, bot, at(14, 20), claimed) == 0
    assert await reminders(client, bot, at(16, 0), claimed) == 0


async def test_no_lunch_reminder_after_lunch_was_logged(client, bot):
    await onboarded(client)
    async with client.app.state.sessionmaker() as session:
        item = MealItem(name="Суп", grams=300, kcal=200, protein=10, fat=5, carbs=20)
        session.add(
            Meal(
                user_id=1001,
                day=utcnow().date(),
                source="text",
                title="Суп",
                created_at=at(12),
                scale=1.0,
                items=[item],
            )
        )
        await session.commit()
    assert await reminders(client, bot, at(14, 10), set()) == 0
    assert await reminders(client, bot, at(20, 40), set()) == 1
    assert "ужин" in bot.sent[0][1]


async def test_weight_reminder_only_after_a_gap(client, bot):
    await onboarded(client)
    assert await reminders(client, bot, at(8, 40), set()) == 0
    async with client.app.state.sessionmaker() as session:
        await session.execute(update(BodyWeight).values(day=utcnow().date() - timedelta(days=4)))
        await session.commit()
    assert await reminders(client, bot, at(8, 40), set()) == 1
    assert "взвеситься" in bot.sent[0][1]


async def test_reminders_respect_settings_and_inactivity(client, bot):
    headers = await onboarded(client)
    await client.patch("/api/me/settings", json={"remind_meals": False}, headers=headers)
    assert await reminders(client, bot, at(14, 10), set()) == 0
    await client.patch("/api/me/settings", json={"remind_meals": True}, headers=headers)
    async with client.app.state.sessionmaker() as session:
        await session.execute(update(User).values(last_seen_at=utcnow() - timedelta(days=30)))
        await session.commit()
    assert await reminders(client, bot, at(14, 10), set()) == 0
    async with client.app.state.sessionmaker() as session:
        assert (await session.scalar(select(User.remind_meals))) is True
