from io import BytesIO
from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select

from belok.bot.handlers.clarify import answer_button
from belok.bot.handlers.voice import voice_meal
from belok.db.models import Meal, User
from belok.i18n import Language
from belok.llm.analyzer import Clarification, FoodItem
from tests.conftest import FakeBot, onboarded

pytestmark = pytest.mark.db


class FakeMessage:
    def __init__(self, duration: int = 5) -> None:
        self.voice = SimpleNamespace(duration=duration)
        self.chat = SimpleNamespace(id=1001)
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)


class FakeVoiceBot:
    """Without widget support, like a Bot API server older than 10.4."""

    async def __call__(self, method) -> None:
        raise TelegramBadRequest(method, "Bad Request: method not found")

    async def send_chat_action(self, chat_id: int, action: str) -> None:
        pass

    async def download(self, file) -> BytesIO:
        return BytesIO(b"ogg")


class FakeStt:
    def __init__(self, text: str) -> None:
        self.text = text

    async def transcribe(self, audio: bytes, language: Language) -> str:
        return self.text


async def run_voice(client, settings, analyzer, stt, message: FakeMessage, bot=None) -> None:
    async with client.app.state.sessionmaker() as session:
        user = await session.get(User, 1001)
        await voice_meal(
            message, bot or FakeVoiceBot(), session, user, settings, Language.RU, analyzer, stt
        )
        await session.commit()


async def test_voice_message_logs_a_meal(client, settings, analyzer):
    await onboarded(client)
    message = FakeMessage()
    await run_voice(client, settings, analyzer, FakeStt("гречка 200 грамм"), message)
    reply = message.answers[0]
    assert "«гречка 200 грамм»" in reply
    assert "Гречка, 200 г: 220 ккал" in reply
    assert "За сегодня: 220 из" in reply
    async with client.app.state.sessionmaker() as session:
        assert (await session.scalar(select(Meal.source))) == "voice"


async def test_voice_without_speech_service_or_too_long(client, settings, analyzer):
    await onboarded(client)
    message = FakeMessage()
    await run_voice(client, settings, analyzer, None, message)
    assert "недоступны" in message.answers[0]
    message = FakeMessage(duration=300)
    await run_voice(client, settings, analyzer, FakeStt("x"), message)
    assert "Слишком длинное" in message.answers[0]


async def test_voice_with_no_food(client, settings, analyzer):
    await onboarded(client)
    analyzer.items = []
    message = FakeMessage()
    await run_voice(client, settings, analyzer, FakeStt("привет как дела"), message)
    assert "не нашёл там еды" in message.answers[0]


class FakeCallback:
    def __init__(self, data: str) -> None:
        self.data = data
        self.message = None
        self.notes: list[str | None] = []

    async def answer(self, text: str | None = None, **kwargs) -> None:
        self.notes.append(text)


async def test_voice_question_answered_with_a_button(client, settings, analyzer):
    await onboarded(client)
    analyzer.question = Clarification(text="Сколько масла?", options=["Без масла", "Ложка"])
    message = FakeMessage()
    await run_voice(client, settings, analyzer, FakeStt("яичница"), message)
    assert "Сколько масла?" in message.answers[-1]

    async with client.app.state.sessionmaker() as session:
        user = await session.get(User, 1001)
        meal_id = await session.scalar(select(Meal.id))
        eggs = FoodItem(name="Яичница", grams=120, kcal=250, protein=14, fat=20, carbs=1)
        analyzer.items = [eggs]
        callback = FakeCallback(f"cq:{meal_id}:0:1")
        await answer_button(callback, FakeBot(), session, user, Language.RU, analyzer)
        assert analyzer.clarified[1:] == ("Сколько масла?", "Ложка")

        stale = FakeCallback(f"cq:{meal_id}:0:0")
        await answer_button(stale, FakeBot(), session, user, Language.RU, analyzer)
        assert stale.notes == ["Этот вопрос уже закрыт."]

    async with client.app.state.sessionmaker() as session:
        meal = await session.get(Meal, meal_id)
        assert meal.question is None
        assert meal.title == "Обед" and meal.items[0].name == "Яичница"
