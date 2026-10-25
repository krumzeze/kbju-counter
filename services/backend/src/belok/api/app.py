from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from belok.api.routes import auth, me, meals, tracking, workouts
from belok.config import Settings
from belok.llm.analyzer import FoodAnalyzer


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    app.state.engine = engine
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    app.state.analyzer = FoodAnalyzer(
        settings.llm_api_key.get_secret_value(), settings.llm_base_url, settings.llm_model
    )
    yield
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
    for module in (auth, me, meals, tracking, workouts):
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
