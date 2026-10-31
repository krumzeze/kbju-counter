import pytest

from belok.catalog import catalog
from tests.conftest import onboarded

pytestmark = pytest.mark.db

BENCH = "Barbell_Bench_Press_-_Medium_Grip"


async def start(client, headers, **body) -> dict:
    response = await client.post("/api/workouts", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def add_exercise(client, headers, workout_id, **ref) -> dict:
    response = await client.post(f"/api/workouts/{workout_id}/exercises", json=ref, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def log(client, headers, workout_id, exercise_id, **values) -> dict:
    body = {"exercise_id": exercise_id, **values}
    response = await client.post(f"/api/workouts/{workout_id}/sets", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def finish(client, headers, workout_id) -> None:
    response = await client.patch(
        f"/api/workouts/{workout_id}", json={"finished": True}, headers=headers
    )
    assert response.status_code == 200, response.text


async def test_catalog_lists_and_details(client):
    headers = await onboarded(client)
    items = (await client.get("/api/catalog", headers=headers)).json()
    assert len(items) == len(catalog())
    detail = (await client.get(f"/api/catalog/{BENCH}", headers=headers)).json()
    assert detail["group"] == "chest"
    assert detail["instructions"]
    assert detail["exercise_id"] is None
    assert (await client.get("/api/catalog/nope", headers=headers)).status_code == 404


async def test_workout_session_flow(client):
    headers = await onboarded(client)
    assert (await client.get("/api/workouts/active", headers=headers)).json() is None

    workout = await start(client, headers)
    assert (await start(client, headers))["id"] == workout["id"]

    workout = await add_exercise(client, headers, workout["id"], catalog_id=BENCH, sets=3)
    [entry] = workout["exercises"]
    assert entry["planned_sets"] == 3 and entry["sets"] == []
    exercise_id = entry["exercise"]["id"]

    first = await log(client, headers, workout["id"], exercise_id, weight_kg=80, reps=8)
    assert first["record"] is False
    await log(client, headers, workout["id"], exercise_id, weight_kg=80, reps=7)
    await finish(client, headers, workout["id"])
    assert (await client.get("/api/workouts/active", headers=headers)).json() is None

    second = await start(client, headers)
    second = await add_exercise(client, headers, second["id"], exercise_id=exercise_id)
    entry = second["exercises"][0]
    assert [(p["weight_kg"], p["reps"]) for p in entry["previous"]] == [(80, 8), (80, 7)]
    record = await log(client, headers, second["id"], exercise_id, weight_kg=85, reps=8)
    assert record["record"] is True

    history = (await client.get("/api/workouts", headers=headers)).json()
    assert [w["sets"] for w in history] == [1, 2]
    assert history[1]["volume_kg"] == 80 * 8 + 80 * 7

    progress = (await client.get(f"/api/exercises/{exercise_id}/progress", headers=headers)).json()
    assert len(progress["points"]) == 1
    assert progress["records"]["weight_kg"] == 85
    assert progress["records"]["e1rm"] == pytest.approx(85 * (1 + 8 / 30), abs=0.1)

    day = (await client.get("/api/day", headers=headers)).json()
    assert len(day["sets"]) == 3
    assert day["activity_kcal"] > 0


async def test_cardio_sets_and_set_editing(client):
    headers = await onboarded(client)
    workout = await start(client, headers)
    exercise = (
        await client.post(
            "/api/exercises", json={"name": "Скакалка", "cardio": True}, headers=headers
        )
    ).json()
    cardio = await log(client, headers, workout["id"], exercise["id"], duration_s=600)
    assert cardio["reps"] is None and cardio["duration_s"] == 600

    patched = await client.patch(
        f"/api/sets/{cardio['id']}", json={"weight_kg": 0, "duration_s": 900}, headers=headers
    )
    assert patched.json()["duration_s"] == 900
    bad = await client.post(
        f"/api/workouts/{workout['id']}/sets", json={"exercise_id": exercise["id"]}, headers=headers
    )
    assert bad.status_code == 422


async def test_removing_exercise_drops_its_sets(client):
    headers = await onboarded(client)
    workout = await start(client, headers)
    workout = await add_exercise(client, headers, workout["id"], catalog_id=BENCH)
    exercise_id = workout["exercises"][0]["exercise"]["id"]
    await log(client, headers, workout["id"], exercise_id, weight_kg=60, reps=10)
    response = await client.delete(
        f"/api/workouts/{workout['id']}/exercises/{exercise_id}", headers=headers
    )
    assert response.json()["exercises"] == []
    assert response.json()["sets"] == 0


async def test_templates(client):
    headers = await onboarded(client)
    body = {"name": "Грудь", "items": [{"catalog_id": BENCH, "sets": 4}]}
    template = (await client.post("/api/templates", json=body, headers=headers)).json()
    assert template["items"][0]["sets"] == 4

    workout = await start(client, headers, template_id=template["id"])
    assert workout["title"] == "Грудь"
    assert workout["exercises"][0]["planned_sets"] == 4

    copy = await client.post(
        "/api/templates", json={"name": "Копия", "workout_id": workout["id"]}, headers=headers
    )
    assert copy.json()["items"][0]["sets"] == 4
    assert (
        await client.delete(f"/api/templates/{template['id']}", headers=headers)
    ).status_code == 204
    assert len((await client.get("/api/templates", headers=headers)).json()) == 1


async def test_analytics(client):
    headers = await onboarded(client)
    workout = await start(client, headers)
    workout = await add_exercise(client, headers, workout["id"], catalog_id=BENCH)
    exercise_id = workout["exercises"][0]["exercise"]["id"]
    for _ in range(3):
        await log(client, headers, workout["id"], exercise_id, weight_kg=70, reps=10)

    data = (await client.get("/api/analytics", headers=headers)).json()
    assert len(data["weeks"]) == 12
    assert data["weeks"][-1] == {
        "start": data["weeks"][-1]["start"],
        "workouts": 1,
        "sets": 3,
        "volume_kg": 2100,
        "cardio_min": 0,
    }
    assert data["streak_weeks"] == 1
    assert data["muscles_week"]["chest"] == 3
    assert data["groups_month"] == {"chest": 3}
    assert data["top"][0]["sets"] == 3


async def test_users_cannot_touch_each_others_workouts(client):
    alice = await onboarded(client, 1)
    bob = await onboarded(client, 2)
    workout = await start(client, alice)
    assert (await client.get(f"/api/workouts/{workout['id']}", headers=bob)).status_code == 404
    response = await client.post(
        f"/api/workouts/{workout['id']}/exercises", json={"catalog_id": BENCH}, headers=bob
    )
    assert response.status_code == 404
