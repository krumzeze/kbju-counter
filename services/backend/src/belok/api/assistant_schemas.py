from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from belok.api.schemas import MealOut
from belok.services.assistant import MAX_CHARS


class AiMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    text: str
    data: dict | None
    created_at: datetime


class AiChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: str
    updated_at: datetime


class AiChatListOut(BaseModel):
    chats: list[AiChatOut]
    messages_left: int
    daily_messages: int
    has_access: bool


class AiChatDetailOut(AiChatOut):
    messages: list[AiMessageOut]


class AiReplyOut(BaseModel):
    chat: AiChatDetailOut
    messages_left: int


class AiMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CHARS)


class DishLoggedOut(BaseModel):
    meal: MealOut
    message: AiMessageOut
