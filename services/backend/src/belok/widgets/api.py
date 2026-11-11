"""Bot API 10.4 widget methods and updates, which aiogram does not ship yet."""

from typing import Any

from aiogram.methods import TelegramMethod
from aiogram.types import InlineKeyboardMarkup, Message
from pydantic import BaseModel


class SendWidget(TelegramMethod[Message]):
    __returning__ = Message
    __api_method__ = "sendWidget"

    chat_id: int
    html: str
    chat_data: str | None = None
    caption: str | None = None
    parse_mode: str | None = None
    allow_queries: bool | None = None
    disable_notification: bool | None = None
    reply_markup: InlineKeyboardMarkup | None = None


class EditMessageWidgetData(TelegramMethod[bool]):
    __returning__ = bool
    __api_method__ = "editMessageWidgetData"

    chat_id: int
    message_id: int
    chat_data: str


class AnswerWidgetQuery(TelegramMethod[bool]):
    __returning__ = bool
    __api_method__ = "answerWidgetQuery"

    widget_query_id: str
    data: str | None = None


class WidgetQueryUser(BaseModel):
    id: int


class WidgetQuery(BaseModel):
    id: str
    from_user: WidgetQueryUser
    message_id: int | None = None
    data: str

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> "WidgetQuery":
        return cls.model_validate({**raw, "from_user": raw.get("from")})
