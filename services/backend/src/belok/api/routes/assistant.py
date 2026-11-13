from aiogram import Bot
from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from belok.api.assistant_schemas import (
    AiChatDetailOut,
    AiChatListOut,
    AiChatOut,
    AiMessageIn,
    AiReplyOut,
)
from belok.api.deps import (
    ActiveUser,
    AssistantDep,
    BotDep,
    SessionDep,
    SettingsDep,
    require,
)
from belok.config import Settings
from belok.db.models import AiChat, User
from belok.llm.assistant import Assistant, AssistantError
from belok.services.access import has_access
from belok.services.assistant import (
    AssistantLimit,
    daily_messages,
    get_chat,
    list_chats,
    messages_left,
    new_chat,
    send_message,
)
from belok.services.features import Feature
from belok.timeutil import utcnow

router = APIRouter(tags=["assistant"], dependencies=[require(Feature.ASSISTANT)])

LIMIT_STATUS = {
    "premium_required": status.HTTP_402_PAYMENT_REQUIRED,
    "daily_limit": status.HTTP_429_TOO_MANY_REQUESTS,
    "too_fast": status.HTTP_429_TOO_MANY_REQUESTS,
    "assistant_busy": status.HTTP_503_SERVICE_UNAVAILABLE,
}


@router.get("/assistant/chats")
async def chats(user: ActiveUser, session: SessionDep, settings: SettingsDep) -> AiChatListOut:
    return AiChatListOut(
        chats=[AiChatOut.model_validate(c) for c in await list_chats(session, user.id)],
        messages_left=await messages_left(session, user, settings),
        daily_messages=daily_messages(user, settings),
        has_access=has_access(user, utcnow()),
    )


@router.get("/assistant/chats/{chat_id}")
async def chat(chat_id: int, user: ActiveUser, session: SessionDep) -> AiChatDetailOut:
    return AiChatDetailOut.model_validate(await _chat(session, user.id, chat_id))


@router.post("/assistant/chats", status_code=status.HTTP_201_CREATED)
async def start_chat(
    body: AiMessageIn,
    user: ActiveUser,
    session: SessionDep,
    settings: SettingsDep,
    assistant: AssistantDep,
    bot: BotDep,
) -> AiReplyOut:
    text = body.text.strip()
    return await _send(session, bot, settings, assistant, user, new_chat(user, text), text)


@router.post("/assistant/chats/{chat_id}/messages")
async def post_message(
    chat_id: int,
    body: AiMessageIn,
    user: ActiveUser,
    session: SessionDep,
    settings: SettingsDep,
    assistant: AssistantDep,
    bot: BotDep,
) -> AiReplyOut:
    current = await _chat(session, user.id, chat_id)
    return await _send(session, bot, settings, assistant, user, current, body.text.strip())


@router.delete("/assistant/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(chat_id: int, user: ActiveUser, session: SessionDep) -> Response:
    await session.delete(await _chat(session, user.id, chat_id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _chat(session: AsyncSession, user_id: int, chat_id: int) -> AiChat:
    found = await get_chat(session, user_id, chat_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "chat_not_found")
    return found


async def _send(
    session: AsyncSession,
    bot: Bot,
    settings: Settings,
    assistant: Assistant,
    user: User,
    current: AiChat,
    text: str,
) -> AiReplyOut:
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "empty_message")
    try:
        await send_message(session, bot, settings, assistant, user, current, text)
    except AssistantLimit as exc:
        raise HTTPException(LIMIT_STATUS[exc.code], exc.code) from exc
    except AssistantError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "assistant_failed") from exc
    return AiReplyOut(
        chat=AiChatDetailOut.model_validate(current),
        messages_left=await messages_left(session, user, settings),
    )
