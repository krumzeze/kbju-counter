import io

import pytest
from PIL import Image
from sqlalchemy import select

from belok.db.models import Meal
from tests.conftest import onboarded

pytestmark = pytest.mark.db

ADMIN, AUTHOR, COOK = 1001, 2002, 3003

CHICKEN = {"name": "Куриное филе", "grams": 600, "kcal": 660, "protein": 138, "fat": 9, "carbs": 0}
BULGUR = {"name": "Булгур", "grams": 200, "kcal": 684, "protein": 24, "fat": 2.6, "carbs": 152}


def recipe_body(**kwargs) -> dict:
    return {
        "title": "Курица с булгуром",
        "portions": 4,
        "cooked_grams": 1000,
        "items": [CHICKEN, BULGUR],
        "steps": [{"text": "Отвари булгур"}, {"text": "Обжарь курицу"}],
        **kwargs,
    }


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 120, 40)).save(out, "PNG")
    return out.getvalue()


async def users(client):
    return (
        await onboarded(client, ADMIN),
        await onboarded(client, AUTHOR),
        await onboarded(client, COOK),
    )


async def upload(client, headers) -> str:
    response = await client.post(
        "/api/recipes/photos", files={"photo": ("a.png", png(), "image/png")}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["photo"]


async def create(client, headers, **kwargs) -> dict:
    response = await client.post("/api/recipes", json=recipe_body(**kwargs), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def published(client, admin, author) -> dict:
    photo = await upload(client, author)
    recipe = await create(client, author, photo=photo)
    response = await client.post(
        f"/api/recipes/{recipe['id']}/publish", json={"author_name": "Аня"}, headers=author
    )
    assert response.json()["status"] == "pending"
    response = await client.post(f"/api/admin/recipes/{recipe['id']}/approve", headers=admin)
    assert response.status_code == 200, response.text
    return response.json()


async def test_private_recipe_is_only_visible_to_its_owner(client):
    _, author, cook = await users(client)
    recipe = await create(client, author)
    assert recipe["status"] == "private"
    assert recipe["per_portion"]["kcal"] == pytest.approx(336)
    assert recipe["raw_grams"] == 800
    assert (await client.get(f"/api/recipes/{recipe['id']}", headers=cook)).status_code == 404
    mine = await client.get("/api/recipes?scope=mine", headers=author)
    assert [r["id"] for r in mine.json()] == [recipe["id"]]
    catalog = await client.get("/api/recipes", headers=cook)
    assert catalog.json() == []


async def test_publishing_needs_photo_and_goes_through_moderation(client, bot):
    admin, author, cook = await users(client)
    recipe = await create(client, author)
    response = await client.post(
        f"/api/recipes/{recipe['id']}/publish", json={"author_name": "Аня"}, headers=author
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "no_photo"

    approved = await published(client, admin, author)
    assert approved["status"] == "public"
    assert approved["author_name"] == "Аня"
    assert any("на модерации" in text for _, text in bot.sent)
    assert any(chat == AUTHOR and "опубликован" in text for chat, text in bot.sent)
    catalog = await client.get("/api/recipes", headers=cook)
    assert [r["id"] for r in catalog.json()] == [approved["id"]]


async def test_rejected_recipe_tells_the_author_why(client, bot):
    admin, author, _ = await users(client)
    recipe = await create(client, author, photo=await upload(client, author))
    await client.post(
        f"/api/recipes/{recipe['id']}/publish", json={"author_name": "Аня"}, headers=author
    )
    pending = await client.get("/api/admin/recipes", headers=admin)
    assert [r["id"] for r in pending.json()] == [recipe["id"]]
    response = await client.post(
        f"/api/admin/recipes/{recipe['id']}/reject", json={"reason": "чужое фото"}, headers=admin
    )
    assert response.json()["status"] == "rejected"
    assert any(chat == AUTHOR and "чужое фото" in text for chat, text in bot.sent)
    own = (await client.get(f"/api/recipes/{recipe['id']}", headers=author)).json()
    assert own["reject_reason"] == "чужое фото"


async def test_admin_recipes_skip_moderation(client):
    admin, *_ = await users(client)
    recipe = await create(client, admin, photo=await upload(client, admin))
    response = await client.post(
        f"/api/recipes/{recipe['id']}/publish", json={"author_name": "Белок"}, headers=admin
    )
    assert response.json()["status"] == "public"


async def test_editing_someone_elses_recipe_means_forking_it(client):
    admin, author, cook = await users(client)
    original = await published(client, admin, author)
    response = await client.put(
        f"/api/recipes/{original['id']}", json=recipe_body(title="Моё"), headers=cook
    )
    assert response.status_code == 404
    fork = (await client.post(f"/api/recipes/{original['id']}/fork", headers=cook)).json()
    assert fork["status"] == "private"
    assert fork["forked_from"] == {"id": original["id"], "title": original["title"]}
    assert fork["photo"] is None
    response = await client.put(
        f"/api/recipes/{fork['id']}", json=recipe_body(title="Без масла"), headers=cook
    )
    assert response.json()["title"] == "Без масла"
    assert (await client.get(f"/api/recipes/{original['id']}", headers=cook)).json()["title"] == (
        original["title"]
    )


async def test_photo_keys_of_other_users_are_refused(client):
    _, author, cook = await users(client)
    photo = await upload(client, author)
    response = await client.post("/api/recipes", json=recipe_body(photo=photo), headers=cook)
    assert response.status_code == 422
    steps = [{"text": "шаг", "photo": photo}]
    response = await client.post("/api/recipes", json=recipe_body(steps=steps), headers=cook)
    assert response.status_code == 422


async def test_step_photos_are_kept_and_dropped_ones_deleted(client, s3):
    _, author, _ = await users(client)
    step_photo = await upload(client, author)
    steps = [{"text": "шаг 1", "photo": step_photo}, {"text": "шаг 2"}]
    recipe = await create(client, author, steps=steps)
    assert recipe["steps"][0]["photo_url"].startswith(f"/api/photos/{step_photo}")
    assert recipe["steps"][1]["photo_url"] is None
    await client.put(
        f"/api/recipes/{recipe['id']}", json=recipe_body(steps=[{"text": "шаг 1"}]), headers=author
    )
    assert step_photo not in s3.objects


async def test_adding_portions_and_grams_to_the_diary(client):
    admin, author, cook = await users(client)
    recipe = await published(client, admin, author)
    url = f"/api/recipes/{recipe['id']}/diary"

    portions = await client.post(
        url, json={"mode": "portions", "portions": 1, "items": [600, 200]}, headers=cook
    )
    assert portions.status_code == 201, portions.text
    assert portions.json()["source"] == "recipe"
    assert portions.json()["totals"]["kcal"] == pytest.approx(336)

    grams = await client.post(
        url, json={"mode": "grams", "grams": 250, "items": [600, 200]}, headers=cook
    )
    assert grams.json()["totals"]["kcal"] == pytest.approx(336)

    less_bulgur = await client.post(
        url,
        json={"mode": "grams", "grams": 300, "cooked_grams": 900, "items": [600, 100]},
        headers=cook,
    )
    assert less_bulgur.json()["totals"]["kcal"] == pytest.approx((660 + 342) / 3)

    no_chicken = await client.post(
        url, json={"mode": "portions", "portions": 2, "items": [0, 200]}, headers=cook
    )
    assert [i["name"] for i in no_chicken.json()["items"]] == ["Булгур"]

    bad = await client.post(
        url, json={"mode": "portions", "portions": 1, "items": [600]}, headers=cook
    )
    assert bad.status_code == 422
    async with client.app.state.sessionmaker() as session:
        ids = (await session.scalars(select(Meal.recipe_id))).all()
    assert ids == [recipe["id"]] * 4


async def test_only_people_who_cooked_it_can_rate(client):
    admin, author, cook = await users(client)
    recipe = await published(client, admin, author)
    url = f"/api/recipes/{recipe['id']}/rating"
    assert (await client.put(url, json={"stars": 5}, headers=cook)).status_code == 403
    await client.post(
        f"/api/recipes/{recipe['id']}/diary",
        json={"mode": "portions", "portions": 1, "items": [600, 200]},
        headers=cook,
    )
    rated = await client.put(url, json={"stars": 4}, headers=cook)
    assert rated.status_code == 200
    body = rated.json()
    assert (body["rating"], body["ratings"], body["my_rating"], body["cooked"]) == (4, 1, 4, 1)
    assert (await client.put(url, json={"stars": 5}, headers=author)).status_code == 403


async def test_favorites_and_filters(client):
    admin, author, cook = await users(client)
    recipe = await published(client, admin, author)
    await client.put(f"/api/recipes/{recipe['id']}/favorite", headers=cook)
    favorites = (await client.get("/api/recipes?scope=favorites", headers=cook)).json()
    assert [r["id"] for r in favorites] == [recipe["id"]]
    assert favorites[0]["is_favorite"] and favorites[0]["favorites"] == 1

    assert len((await client.get("/api/recipes?filters=protein", headers=cook)).json()) == 1
    assert len((await client.get("/api/recipes?filters=light", headers=cook)).json()) == 1
    assert (await client.get("/api/recipes?q=булгур", headers=cook)).json()[0]["id"] == recipe["id"]
    assert (await client.get("/api/recipes?q=паста", headers=cook)).json() == []

    await client.delete(f"/api/recipes/{recipe['id']}/favorite", headers=cook)
    assert (await client.get("/api/recipes?scope=favorites", headers=cook)).json() == []


async def test_suggestions_fit_the_rest_of_the_day(client):
    admin, author, cook = await users(client)
    recipe = await published(client, admin, author)
    found = (await client.get("/api/recipes/suggestions", headers=cook)).json()
    assert [r["id"] for r in found] == [recipe["id"]]


async def test_deleting_a_recipe_keeps_logged_meals(client, s3):
    admin, author, cook = await users(client)
    recipe = await published(client, admin, author)
    await client.post(
        f"/api/recipes/{recipe['id']}/diary",
        json={"mode": "portions", "portions": 1, "items": [600, 200]},
        headers=cook,
    )
    assert (await client.delete(f"/api/recipes/{recipe['id']}", headers=cook)).status_code == 404
    assert (await client.delete(f"/api/recipes/{recipe['id']}", headers=author)).status_code == 204
    assert recipe["photo"] not in s3.objects
    async with client.app.state.sessionmaker() as session:
        meal = await session.scalar(select(Meal))
    assert meal.recipe_id is None and meal.title == recipe["title"]


async def test_implausible_items_are_refused(client):
    _, author, _ = await users(client)
    item = {**CHICKEN, "kcal": 6000}
    response = await client.post("/api/recipes", json=recipe_body(items=[item]), headers=author)
    assert response.status_code == 422


async def test_ingredients_from_text(client, analyzer):
    _, author, _ = await users(client)
    response = await client.post(
        "/api/recipes/ingredients", json={"text": "гречка 200 г"}, headers=author
    )
    assert response.status_code == 200, response.text
    assert response.json()[0]["name"] == "Гречка"


async def cook_query(client, bot, data: str) -> str:
    from belok.db.models import User
    from belok.services import widgets
    from belok.widgets.api import WidgetQuery

    raw = {"id": "q", "from": {"id": COOK}, "data": data, "message_id": 5}
    async with client.app.state.sessionmaker() as session:
        user = await session.get(User, COOK)
        await widgets.answer_query(bot, session, user, WidgetQuery.parse(raw))
    return next(c for c in reversed(bot.calls) if c.__api_method__ == "answerWidgetQuery").data


async def test_cooking_widget_logs_the_dish(client, bot):
    admin, author, cook = await users(client)
    recipe = await published(client, admin, author)
    response = await client.post(f"/api/recipes/{recipe['id']}/cook", headers=cook)
    assert response.status_code == 204, response.text
    widget = bot.calls[-1]
    assert widget.__api_method__ == "sendWidget"
    assert "Курица с булгуром" in widget.html and "/*DATA*/" not in widget.html
    assert "Отвари булгур" in widget.html

    rid = recipe["id"]
    assert await cook_query(client, bot, f"c:{rid}:p:1") == "ok"
    assert await cook_query(client, bot, f"c:{rid}:g:250:1000:600,0") == "ok"
    assert await cook_query(client, bot, f"c:{rid}:p:1:600") == "error"
    assert await cook_query(client, bot, f"c:{rid}:x:1") == "error"
    async with client.app.state.sessionmaker() as session:
        meals = (await session.scalars(select(Meal).order_by(Meal.id))).all()
    assert [round(m.totals().kcal) for m in meals] == [336, 165]


def test_long_recipes_still_fit_a_widget():
    import random
    import zlib
    from types import SimpleNamespace

    from belok.db.models import Recipe, RecipeItem
    from belok.services.widgets import cook_html

    rng = random.Random(1)  # noqa: S311
    words = [
        "нарежь",
        "обжарь",
        "добавь",
        "перемешай",
        "посоли",
        "томи",
        "на",
        "сковороде",
        "до",
        "золотистой",
        "корочки",
        "минут",
        "огонь",
        "лук",
        "морковь",
        "чеснок",
        "сливки",
        "соус",
    ]
    steps = [
        {"text": " ".join(rng.choice(words) for _ in range(90)), "photo": None} for _ in range(15)
    ]
    items = [
        RecipeItem(
            position=k, name=f"Продукт номер {k}", grams=150, kcal=200, protein=10, fat=5, carbs=20
        )
        for k in range(25)
    ]
    recipe = Recipe(
        id=1, title="Очень длинный рецепт", portions=6, cooked_grams=None, steps=steps, items=items
    )
    code = cook_html(SimpleNamespace(language=None), recipe).encode()
    assert len(code) <= 32768 and len(zlib.compress(code, 9)) <= 4096
    assert b'"x": true' in code
