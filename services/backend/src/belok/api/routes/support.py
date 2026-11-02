from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from belok.api.deps import BotDep, CurrentUser, SessionDep
from belok.services import support

router = APIRouter(tags=["support"])


class SupportMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    from_admin: bool
    text: str


class SupportMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=support.MAX_TEXT)


@router.get("/support")
async def get_support(user: CurrentUser, session: SessionDep) -> list[SupportMessageOut]:
    return [SupportMessageOut.model_validate(m) for m in await support.history(session, user.id)]


@router.post("/support", status_code=status.HTTP_201_CREATED)
async def post_support(
    body: SupportMessageIn, user: CurrentUser, session: SessionDep, bot: BotDep
) -> SupportMessageOut:
    text = body.text.strip()
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "empty_message")
    try:
        message = await support.submit(session, bot, user, text, "web")
    except support.TooManyMessages as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_messages") from exc
    return SupportMessageOut.model_validate(message)
