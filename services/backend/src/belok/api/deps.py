import logging
from collections.abc import AsyncIterator
from typing import Annotated

from aiogram import Bot
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from belok.api.auth import InvalidAuth, decode_token
from belok.config import Settings
from belok.db.models import User
from belok.llm.analyzer import FoodAnalyzer
from belok.llm.assistant import Assistant
from belok.llm.speech import SpeechToText
from belok.services import features
from belok.services.features import Feature
from belok.services.photos import PhotoStore
from belok.services.products import FoodDatabase
from belok.services.tribute import TributeCatalog
from belok.services.users import SEEN_RESOLUTION
from belok.services.widgets import refresh_day_card
from belok.timeutil import utcnow

log = logging.getLogger(__name__)

bearer = HTTPBearer(auto_error=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_analyzer(request: Request) -> FoodAnalyzer:
    return request.app.state.analyzer


def get_assistant(request: Request) -> Assistant:
    return request.app.state.assistant


def get_food_db(request: Request) -> FoodDatabase:
    return request.app.state.food_db


def get_stt(request: Request) -> SpeechToText | None:
    return request.app.state.stt


def get_photos(request: Request) -> PhotoStore | None:
    return request.app.state.photos


def get_bot(request: Request) -> Bot:
    return request.app.state.bot


def get_tribute(request: Request) -> TributeCatalog:
    return request.app.state.tribute


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
AnalyzerDep = Annotated[FoodAnalyzer, Depends(get_analyzer)]
AssistantDep = Annotated[Assistant, Depends(get_assistant)]
FoodDbDep = Annotated[FoodDatabase, Depends(get_food_db)]
SttDep = Annotated[SpeechToText | None, Depends(get_stt)]
PhotosDep = Annotated[PhotoStore | None, Depends(get_photos)]
BotDep = Annotated[Bot, Depends(get_bot)]
TributeDep = Annotated[TributeCatalog, Depends(get_tribute)]


async def current_user(
    session: SessionDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
    try:
        user_id = decode_token(credentials.credentials, settings.api_secret.get_secret_value())
    except InvalidAuth as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token") from exc
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    if user.is_blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "blocked")
    if user.last_seen_at is None or utcnow() - user.last_seen_at > SEEN_RESOLUTION:
        user.last_seen_at = utcnow()
        await session.commit()
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def token_user_id(request: Request) -> int | None:
    """User id from a valid bearer token, without touching the database."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        return decode_token(token, get_settings(request).api_secret.get_secret_value())
    except InvalidAuth:
        return None


async def active_user(user: CurrentUser) -> User:
    if not user.profile_complete:
        raise HTTPException(status.HTTP_409_CONFLICT, "profile_incomplete")
    return user


ActiveUser = Annotated[User, Depends(active_user)]


async def admin_user(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin_only")
    return user


AdminUser = Annotated[User, Depends(admin_user)]


def require(feature: Feature):
    async def check(session: SessionDep) -> None:
        if not await features.enabled(session, feature):
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "feature_disabled")

    return Depends(check)


async def _refresh_day_card(app: FastAPI, user_id: int) -> None:
    try:
        async with app.state.sessionmaker() as session:
            user = await session.get(User, user_id)
            if user is not None:
                await refresh_day_card(app.state.bot, session, user)
    except Exception:
        log.exception("day card refresh for %s failed", user_id)


def refresh_day_card_later(request: Request, user: CurrentUser, tasks: BackgroundTasks) -> None:
    """After a successful change, update the user's day card in the bot chat."""
    if request.method != "GET" and user.day_card_message_id is not None:
        tasks.add_task(_refresh_day_card, request.app, user.id)
