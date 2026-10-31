from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from belok.api.routes import admin, auth, me, meals, payments, tracking, workouts
from belok.config import Settings
from belok.llm.analyzer import FoodAnalyzer
from belok.services.tribute import TributeCatalog


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    app.state.engine = engine
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    app.state.analyzer = FoodAnalyzer(settings.llm_api_key.get_secret_value(), settings.llm_model)
    app.state.bot = Bot(
        settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    yield
    await app.state.bot.session.close()
    await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    if settings.api_secret is None or len(settings.api_secret.get_secret_value()) < 32:
        raise RuntimeError("API_SECRET must be set to at least 32 characters")

    app = FastAPI(
        title="Belok API",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.tribute = TributeCatalog.from_settings(settings)
    for module in (admin, auth, me, meals, payments, tracking, workouts):
        app.include_router(module.router, prefix="/api")

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz() -> dict[str, str]:
        async with app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}

    return app
