from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from belok.api.auth import InvalidAuth, decode_token
from belok.config import Settings
from belok.db.models import User
from belok.llm.analyzer import FoodAnalyzer
from belok.services.access import has_access
from belok.timeutil import utcnow

bearer = HTTPBearer(auto_error=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_analyzer(request: Request) -> FoodAnalyzer:
    return request.app.state.analyzer


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
AnalyzerDep = Annotated[FoodAnalyzer, Depends(get_analyzer)]


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
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def active_user(user: CurrentUser) -> User:
    if not user.profile_complete:
        raise HTTPException(status.HTTP_409_CONFLICT, "profile_incomplete")
    if not has_access(user, utcnow()):
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "access_expired")
    return user


ActiveUser = Annotated[User, Depends(active_user)]
