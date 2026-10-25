import time

import pytest

from belok.api.auth import (
    InvalidAuth,
    decode_token,
    issue_token,
    verify_login_widget,
    verify_webapp_init_data,
)
from tests.telegram_signing import BOT_TOKEN, sign_init_data, sign_widget


def test_valid_init_data():
    identity = verify_webapp_init_data(sign_init_data(42, "karim"), BOT_TOKEN)
    assert identity.id == 42
    assert identity.username == "karim"


def test_init_data_with_wrong_token_is_rejected():
    with pytest.raises(InvalidAuth):
        verify_webapp_init_data(sign_init_data(42), "999:other")


def test_tampered_init_data_is_rejected():
    tampered = sign_init_data(42).replace("%22id%22%3A+42", "%22id%22%3A+43")
    with pytest.raises(InvalidAuth):
        verify_webapp_init_data(tampered, BOT_TOKEN)


def test_expired_init_data_is_rejected():
    old = sign_init_data(42, auth_date=int(time.time()) - 2 * 86400)
    with pytest.raises(InvalidAuth):
        verify_webapp_init_data(old, BOT_TOKEN)


def test_valid_login_widget():
    assert verify_login_widget(sign_widget(7), BOT_TOKEN).id == 7


def test_login_widget_with_bad_hash_is_rejected():
    data = sign_widget(7) | {"hash": "0" * 64}
    with pytest.raises(InvalidAuth):
        verify_login_widget(data, BOT_TOKEN)


def test_token_roundtrip():
    secret, other = "s" * 32, "o" * 32
    assert decode_token(issue_token(42, secret), secret) == 42
    with pytest.raises(InvalidAuth):
        decode_token(issue_token(42, secret), other)
