from html import escape

from aiogram import Bot
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from belok.api.auth import (
    InvalidAuth,
    TelegramIdentity,
    issue_token,
    verify_login_widget,
    verify_webapp_init_data,
)
from belok.api.deps import BotDep, SessionDep, SettingsDep
from belok.api.schemas import PublicConfigOut, TokenOut, WebAppAuthIn, WidgetAuthIn
from belok.config import Settings
from belok.db.models import User
from belok.services.notify import admin_recipients, send_all
from belok.services.users import get_or_create_user

router = APIRouter(tags=["auth"])


@router.get("/config")
async def public_config(settings: SettingsDep) -> PublicConfigOut:
    return PublicConfigOut(bot_username=settings.bot_username)


@router.post("/auth/webapp")
async def auth_webapp(
    body: WebAppAuthIn,
    session: SessionDep,
    settings: SettingsDep,
    bot: BotDep,
    background: BackgroundTasks,
) -> TokenOut:
    try:
        identity = verify_webapp_init_data(body.init_data, settings.bot_token.get_secret_value())
    except InvalidAuth as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_init_data") from exc
    return await _login(session, settings, bot, background, identity)


@router.post("/auth/widget")
async def auth_widget(
    body: WidgetAuthIn,
    session: SessionDep,
    settings: SettingsDep,
    bot: BotDep,
    background: BackgroundTasks,
) -> TokenOut:
    try:
        identity = verify_login_widget(
            body.model_dump(exclude_none=True), settings.bot_token.get_secret_value()
        )
    except InvalidAuth as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_login") from exc
    return await _login(session, settings, bot, background, identity)


async def _login(
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
    background: BackgroundTasks,
    identity: TelegramIdentity,
) -> TokenOut:
    user, created = await get_or_create_user(
        session,
        settings,
        identity.id,
        identity.username,
        identity.first_name,
        identity.start_param,
    )
    if user.is_blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "blocked")
    if created:
        recipients = await admin_recipients(session, "new_users", exclude=user.id)
        background.add_task(send_all, bot, recipients, _new_user_text(user))
    await session.commit()
    return TokenOut(token=issue_token(user.id, settings.api_secret.get_secret_value()))


def _new_user_text(user: User) -> str:
    name = f"@{user.username}" if user.username else escape(user.first_name or str(user.id))
    source = f"\nИсточник: {escape(user.source)}" if user.source else ""
    return f"👤 Новый пользователь: {name}{source}"
