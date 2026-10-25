from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from belok.api.auth import (
    InvalidAuth,
    TelegramIdentity,
    issue_token,
    verify_login_widget,
    verify_webapp_init_data,
)
from belok.api.deps import SessionDep, SettingsDep
from belok.api.schemas import PublicConfigOut, TokenOut, WebAppAuthIn, WidgetAuthIn
from belok.config import Settings
from belok.services.users import get_or_create_user

router = APIRouter(tags=["auth"])


@router.get("/config")
async def public_config(settings: SettingsDep) -> PublicConfigOut:
    return PublicConfigOut(bot_username=settings.bot_username)


@router.post("/auth/webapp")
async def auth_webapp(body: WebAppAuthIn, session: SessionDep, settings: SettingsDep) -> TokenOut:
    try:
        identity = verify_webapp_init_data(body.init_data, settings.bot_token.get_secret_value())
    except InvalidAuth as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_init_data") from exc
    return await _login(session, settings, identity)


@router.post("/auth/widget")
async def auth_widget(body: WidgetAuthIn, session: SessionDep, settings: SettingsDep) -> TokenOut:
    try:
        identity = verify_login_widget(
            body.model_dump(exclude_none=True), settings.bot_token.get_secret_value()
        )
    except InvalidAuth as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_login") from exc
    return await _login(session, settings, identity)


async def _login(session: AsyncSession, settings: Settings, identity: TelegramIdentity) -> TokenOut:
    user = await get_or_create_user(
        session, identity.id, identity.username, settings.trial_days, settings.default_timezone
    )
    await session.commit()
    return TokenOut(token=issue_token(user.id, settings.api_secret.get_secret_value()))
