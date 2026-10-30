from datetime import UTC, datetime

from aiogram.types import Chat, Message, Update

from belok.bot.middlewares import _start_param


def update_with(text: str) -> Update:
    message = Message(
        message_id=1, date=datetime.now(UTC), chat=Chat(id=1, type="private"), text=text
    )
    return Update(update_id=1, message=message)


def test_start_param_is_read_from_deep_link():
    assert _start_param(update_with("/start r_ABC123")) == "r_ABC123"


def test_plain_start_and_other_commands_have_no_param():
    assert _start_param(update_with("/start")) is None
    assert _start_param(update_with("/promo X")) is None
