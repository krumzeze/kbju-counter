import json
import zlib
from importlib.resources import files

import pytest
from aiogram.types import Update
from sqlalchemy import func, select

from belok.bot.middlewares import UserMiddleware, WidgetQueryMiddleware
from belok.db.models import BodyWeight, DailyActivity, Meal, MealItem, User
from belok.services import widgets
from belok.timeutil import local_today
from belok.widgets import html
from belok.widgets.api import WidgetQuery
from tests.conftest import FakeBot, onboarded
from tests.test_voice import FakeMessage, FakeStt, FakeVoiceBot, run_voice

NAMES = ("meal", "day", "weight", "usual")


@pytest.mark.parametrize("name", NAMES)
def test_widget_fits_telegram_limits(name):
    raw = html(name).encode()
    assert len(raw) <= 32768
    assert len(zlib.compress(raw, 9)) <= 4096
    assert b"\0" not in raw
    assert files("belok.widgets").joinpath(f"{name}.html").is_file()


class WidgetVoiceBot(FakeVoiceBot, FakeBot):
    def __init__(self) -> None:
        FakeBot.__init__(self)

    __call__ = FakeBot.__call__


def state_of(call) -> dict:
    return json.loads(call.chat_data)


async def add_meal(session, user_id: int, title: str = "Омлет", **kwargs) -> Meal:
    user = await session.get(User, user_id)
    meal = Meal(
        user_id=user_id,
        day=kwargs.get("day", local_today(user.timezone)),
        source="text",
        title=title,
        scale=kwargs.get("scale", 1.0),
        items=[
            MealItem(name="Яйца", grams=100, kcal=150, protein=12, fat=10, carbs=1),
            MealItem(name="Сыр", grams=30, kcal=110, protein=7, fat=9, carbs=0),
        ],
    )
    session.add(meal)
    await session.commit()
    return meal


async def ask(client, bot: FakeBot, data: str, message_id: int | None = 7) -> str:
    raw = {"id": "q1", "from": {"id": 1001}, "data": data, "message_id": message_id}
    async with client.app.state.sessionmaker() as session:
        user = await session.get(User, 1001)
        await widgets.answer_query(bot, session, user, WidgetQuery.parse(raw))
    answer = next(c for c in reversed(bot.calls) if c.__api_method__ == "answerWidgetQuery")
    return answer.data


@pytest.mark.db
async def test_voice_meal_comes_as_an_editable_widget(client, settings, analyzer):
    await onboarded(client)
    message, bot = FakeMessage(), WidgetVoiceBot()
    await run_voice(client, settings, analyzer, FakeStt("гречка 200 грамм"), message, bot)
    assert message.answers == []
    [widget] = bot.calls
    assert widget.html == html("meal")
    assert widget.allow_queries
    assert "«гречка 200 грамм»" in widget.caption
    state = state_of(widget)
    assert state["i"] == [["Гречка", 200, 220.0, 8.0, 2.0, 42.0]]
    assert state["e"] == 0
    assert state["K"] > 0


@pytest.mark.db
async def test_voice_falls_back_to_text_without_widgets(client, settings, analyzer):
    await onboarded(client)
    message = FakeMessage()
    await run_voice(client, settings, analyzer, FakeStt("гречка 200 грамм"), message)
    assert "Гречка, 200 г: 220 ккал" in message.answers[0]


@pytest.mark.db
async def test_saving_grams_resizes_and_removes_items(client, bot):
    await onboarded(client)
    async with client.app.state.sessionmaker() as session:
        meal = await add_meal(session, 1001, scale=2.0)
    assert await ask(client, bot, f"s:{meal.id}:150,0") == "ok"
    async with client.app.state.sessionmaker() as session:
        saved = await session.get(Meal, meal.id)
        [item] = saved.items
        assert item.name == "Яйца"
        assert saved.totals().kcal == pytest.approx(225)
    edit = next(c for c in bot.calls if c.__api_method__ == "editMessageWidgetData")
    assert edit.message_id == 7
    assert state_of(edit)["i"] == [["Яйца", 150, 225.0, 18.0, 15.0, 1.5]]


@pytest.mark.db
async def test_removing_every_item_deletes_the_meal(client, bot):
    await onboarded(client)
    async with client.app.state.sessionmaker() as session:
        meal = await add_meal(session, 1001)
    assert await ask(client, bot, f"s:{meal.id}:0,0") == "ok"
    async with client.app.state.sessionmaker() as session:
        assert await session.get(Meal, meal.id) is None
    edit = next(c for c in bot.calls if c.__api_method__ == "editMessageWidgetData")
    assert state_of(edit)["x"] == 1


@pytest.mark.db
@pytest.mark.parametrize("data", ["s:{id}:150", "s:{id}:150,9999", "s:{id}:a,b", "s:0:1,1", "zz"])
async def test_invalid_queries_change_nothing(client, bot, data):
    await onboarded(client)
    await onboarded(client, 1002)
    async with client.app.state.sessionmaker() as session:
        meal = await add_meal(session, 1001)
        other = await add_meal(session, 1002)
    assert await ask(client, bot, data.format(id=meal.id)) == "error"
    assert await ask(client, bot, f"s:{other.id}:1,1") == "error"
    async with client.app.state.sessionmaker() as session:
        assert len((await session.get(Meal, meal.id)).items) == 2


@pytest.mark.db
async def test_quick_actions(client, bot):
    await onboarded(client)
    async with client.app.state.sessionmaker() as session:
        meal = await add_meal(session, 1001)
    assert await ask(client, bot, "w:250") == "ok"
    assert await ask(client, bot, f"r:{meal.id}") == "ok"
    assert await ask(client, bot, "wt:79.4") == "ok"
    assert await ask(client, bot, "u") == "ok"
    assert await ask(client, bot, "w:5000") == "error"
    async with client.app.state.sessionmaker() as session:
        assert await session.scalar(select(DailyActivity.water_ml)) == 250
        assert await session.scalar(select(func.count()).select_from(Meal)) == 1
        weights = (await session.scalars(select(BodyWeight.weight_kg))).all()
        assert 79.4 in weights


@pytest.mark.db
async def test_day_card_is_pinned_and_follows_app_changes(client, bot):
    headers = await onboarded(client)
    response = await client.post("/api/me/day-card", headers=headers)
    assert response.status_code == 204
    card = bot.calls[-1]
    assert card.html == html("day")
    assert state_of(card)["k"] == 0

    response = await client.post("/api/water/today", json={"delta_ml": 300}, headers=headers)
    assert response.status_code == 200
    edit = bot.calls[-1]
    assert edit.__api_method__ == "editMessageWidgetData"
    assert state_of(edit)["w"] == 300
    async with client.app.state.sessionmaker() as session:
        assert (await session.get(User, 1001)).day_card_message_id == edit.message_id


@pytest.mark.db
async def test_widget_query_update_is_answered(client, bot):
    await onboarded(client)
    update = Update.model_validate(
        {"update_id": 1, "widget_query": {"id": "q9", "from": {"id": 1001}, "data": "w:250"}}
    )

    async def handler(event, data):
        raise AssertionError("widget queries must not reach handlers")

    async with client.app.state.sessionmaker() as session:
        await WidgetQueryMiddleware()(handler, update, {"session": session, "bot": bot})
    assert bot.calls[-1].widget_query_id == "q9"
    assert bot.calls[-1].data == "ok"


@pytest.mark.db
async def test_usual_meals_follow_the_time_slot(client):
    await onboarded(client)
    from datetime import datetime, time, timedelta
    from zoneinfo import ZoneInfo

    msk = ZoneInfo("Europe/Moscow")
    async with client.app.state.sessionmaker() as session:
        user = await session.get(User, 1001)
        user.timezone = "Europe/Moscow"
        today = local_today(user.timezone)
        for n, (title, at) in enumerate(
            [("Суп", time(13)), ("Суп", time(13, 30)), ("Паста", time(19)), ("Салат", time(12))]
        ):
            day = today - timedelta(days=n + 1)
            meal = await add_meal(session, 1001, title, day=day)
            meal.created_at = datetime.combine(day, at, msk)
        await session.commit()
        meals = await widgets.usual_meals(session, user, time(11), time(17), today)
    assert [m.title for m in meals] == ["Суп", "Салат"]


async def test_bot_own_service_messages_are_ignored(settings):
    pinned = Update.model_validate(
        {
            "update_id": 2,
            "message": {
                "message_id": 3,
                "date": 0,
                "chat": {"id": 1001, "type": "private"},
                "from": {"id": 42, "is_bot": True, "first_name": "Belok"},
                "pinned_message": {
                    "message_id": 2,
                    "date": 0,
                    "chat": {"id": 1001, "type": "private"},
                },
            },
        }
    )

    async def handler(event, data):
        raise AssertionError("the bot must not handle its own messages")

    data = {"event_from_user": pinned.message.from_user}
    assert await UserMiddleware(settings)(handler, pinned, data) is None
