import io
from datetime import timedelta

import pytest
from PIL import Image
from sqlalchemy import select, update

from belok.db.models import Meal, PhotoEval
from belok.services.photos import PhotoStore, make_thumbnail
from tests.conftest import onboarded


def jpeg(size: tuple[int, int] = (2000, 1000)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (200, 120, 40)).save(out, "JPEG")
    return out.getvalue()


async def add_photo_meal(client, headers) -> dict:
    response = await client.post(
        "/api/meals/photo", files={"photo": ("food.jpg", jpeg(), "image/jpeg")}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def session_of(client):
    return client.app.state.sessionmaker()


def test_thumbnail_is_small_webp():
    thumb = make_thumbnail(jpeg())
    with Image.open(io.BytesIO(thumb)) as img:
        assert img.format == "WEBP"
        assert img.size == (800, 400)
        assert "exif" not in img.info


def test_photo_url_is_stable_within_a_day_and_checked():
    store = PhotoStore(None, "b", b"secret")
    key = "meals/1/" + "a" * 32 + ".webp"
    now = 1_800_000_000
    assert store.url(key, now) == store.url(key, now + 60)
    query = store.url(key, now).split("?")[1]
    params = dict(p.split("=") for p in query.split("&"))
    exp = int(params["exp"])
    assert exp - now > 24 * 3600
    assert store.verify(key, exp, params["sig"], now)
    assert not store.verify(key, exp, params["sig"], exp + 1)
    assert not store.verify(key.replace("1", "2", 1), exp, params["sig"], now)


@pytest.mark.db
async def test_photo_meal_keeps_thumbnail(client, s3):
    headers = await onboarded(client)
    meal = await add_photo_meal(client, headers)
    assert len(s3.objects) == 1
    key = next(iter(s3.objects))
    assert key.startswith("meals/1001/")

    url = meal["photo_url"]
    response = await client.get(url)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert response.content == s3.objects[key]

    day = (await client.get("/api/day", headers=headers)).json()
    assert day["meals"][0]["photo_url"] == url
    assert (await client.get(url.replace("sig=", "sig=0"))).status_code == 404


@pytest.mark.db
async def test_appended_payload_is_not_stored(client, s3):
    headers = await onboarded(client)
    payload = b"#!/bin/sh\nrm -rf /\n"
    response = await client.post(
        "/api/meals/photo",
        files={"photo": ("food.jpg", jpeg() + payload, "image/jpeg")},
        headers=headers,
    )
    assert response.status_code == 201
    (stored,) = s3.objects.values()
    assert payload not in stored
    assert stored[:4] == b"RIFF"


@pytest.mark.db
async def test_old_photos_have_no_url(client):
    headers = await onboarded(client)
    meal = await add_photo_meal(client, headers)
    async with await session_of(client) as session:
        await session.execute(
            update(Meal)
            .where(Meal.id == meal["id"])
            .values(created_at=Meal.created_at - timedelta(days=91))
        )
        await session.commit()
    day = (await client.get("/api/day", headers=headers)).json()
    assert day["meals"][0]["photo_url"] is None


@pytest.mark.db
async def test_deleting_meal_deletes_photo(client, s3):
    headers = await onboarded(client)
    meal = await add_photo_meal(client, headers)
    assert (await client.delete(f"/api/meals/{meal['id']}", headers=headers)).status_code == 204
    assert s3.objects == {}


@pytest.mark.db
async def test_repeat_does_not_share_photo(client):
    headers = await onboarded(client)
    meal = await add_photo_meal(client, headers)
    copy = (await client.post(f"/api/meals/{meal['id']}/repeat", headers=headers)).json()
    assert copy["photo_url"] is None


@pytest.mark.db
async def test_correction_without_consent_keeps_nothing(client, s3):
    headers = await onboarded(client)
    meal = await add_photo_meal(client, headers)
    item = meal["items"][0]["id"]
    await client.patch(
        f"/api/meals/{meal['id']}/items/{item}", json={"grams": 150}, headers=headers
    )
    assert not any(k.startswith("eval/") for k in s3.objects)


@pytest.mark.db
async def test_corrected_photo_kept_for_eval_with_consent(client, s3):
    headers = await onboarded(client)
    me = await client.patch("/api/me/settings", json={"photo_eval_consent": True}, headers=headers)
    assert me.json()["photo_eval_consent"] is True
    meal = await add_photo_meal(client, headers)
    item = meal["items"][0]["id"]
    for grams in (150, 120):
        response = await client.patch(
            f"/api/meals/{meal['id']}/items/{item}", json={"grams": grams}, headers=headers
        )
        assert response.status_code == 200

    eval_key = f"eval/1001/{meal['id']}.webp"
    assert eval_key in s3.objects
    async with await session_of(client) as session:
        sample = (await session.scalars(select(PhotoEval))).one()
    assert sample.photo_key == eval_key
    assert sample.original["items"][0]["grams"] == 200

    await client.delete(f"/api/meals/{meal['id']}", headers=headers)
    assert s3.objects == {}


@pytest.mark.db
async def test_withdrawing_consent_drops_eval_photos(client, s3):
    headers = await onboarded(client)
    await client.patch("/api/me/settings", json={"photo_eval_consent": True}, headers=headers)
    meal = await add_photo_meal(client, headers)
    await client.post(f"/api/meals/{meal['id']}/refine", json={"text": "это рис"}, headers=headers)
    assert any(k.startswith("eval/") for k in s3.objects)

    await client.patch("/api/me/settings", json={"photo_eval_consent": False}, headers=headers)
    assert not any(k.startswith("eval/") for k in s3.objects)
    async with await session_of(client) as session:
        assert (await session.scalars(select(PhotoEval))).all() == []
    assert len(s3.objects) == 1


@pytest.mark.db
async def test_deleting_user_deletes_their_photos(client, s3):
    admin = await onboarded(client, 1)
    headers = await onboarded(client, 1001)
    await client.patch("/api/me/settings", json={"photo_eval_consent": True}, headers=headers)
    meal = await add_photo_meal(client, headers)
    await client.post(f"/api/meals/{meal['id']}/refine", json={"text": "это рис"}, headers=headers)
    other = await add_photo_meal(client, admin)
    assert len(s3.objects) == 3

    assert (await client.delete("/api/admin/users/1001", headers=admin)).status_code == 204
    assert list(s3.objects) == [next(k for k in s3.objects if k.startswith("meals/1/"))]
    assert (await client.get(other["photo_url"])).status_code == 200
