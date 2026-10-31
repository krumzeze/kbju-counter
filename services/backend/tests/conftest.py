import asyncio
import os
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from belok.api.app import create_app
from belok.config import Settings
from belok.db.models import Base
from belok.i18n import Language
from belok.llm.analyzer import AnalysisResult, FoodAnalysis, FoodItem
from tests.telegram_signing import BOT_TOKEN, sign_init_data

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def pytest_collection_modifyitems(config, items):
    if TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL is not set")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session", autouse=True)
def schema():
    if not TEST_DATABASE_URL:
        yield
        return

    async def reset():
        engine = create_async_engine(TEST_DATABASE_URL)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(reset())
    yield


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.fail_for: dict[int, Exception] = {}

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        if chat_id in self.fail_for:
            raise self.fail_for[chat_id]
        self.sent.append((chat_id, text))


class FakeAnalyzer:
    model = "fake/model"

    def __init__(self) -> None:
        self.items = [FoodItem(name="Гречка", grams=200, kcal=220, protein=8, fat=2, carbs=42)]

    async def from_photo(
        self, image: bytes, caption: str | None, language: Language
    ) -> AnalysisResult:
        return self._result()

    async def from_text(self, text: str, language: Language) -> AnalysisResult:
        return self._result()

    def _result(self) -> AnalysisResult:
        return AnalysisResult(
            analysis=FoodAnalysis(title="Обед", items=self.items),
            model=self.model,
            prompt_tokens=1000,
            completion_tokens=200,
            cost_usd=0.001,
            latency_ms=5,
        )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        bot_token=BOT_TOKEN,
        llm_api_key="unused",
        api_secret="test-secret-" + "x" * 32,
        database_url=TEST_DATABASE_URL or "",
        daily_analysis_limit=3,
        default_timezone="UTC",
    )


@pytest.fixture
def analyzer() -> FakeAnalyzer:
    return FakeAnalyzer()


@pytest.fixture
def bot() -> FakeBot:
    return FakeBot()


@pytest.fixture
async def client(
    settings: Settings, analyzer: FakeAnalyzer, bot: FakeBot
) -> AsyncIterator[httpx.AsyncClient]:
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    app = create_app(settings)
    app.state.engine = engine
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    app.state.analyzer = analyzer
    app.state.bot = bot
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        c.app = app
        yield c
    await engine.dispose()


async def login(
    client: httpx.AsyncClient, user_id: int = 1001, start_param: str | None = None
) -> dict[str, str]:
    init_data = sign_init_data(user_id, start_param=start_param)
    response = await client.post("/api/auth/webapp", json={"init_data": init_data})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


PROFILE = {"sex": "m", "age": 30, "height_cm": 180, "weight_kg": 80, "goal": "maintain"}


async def onboarded(client: httpx.AsyncClient, user_id: int = 1001) -> dict[str, str]:
    headers = await login(client, user_id)
    response = await client.put("/api/me/profile", json=PROFILE, headers=headers)
    assert response.status_code == 200, response.text
    return headers
