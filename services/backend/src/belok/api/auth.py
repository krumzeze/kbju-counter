import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import parse_qsl

import jwt

TOKEN_TTL = timedelta(days=30)
MAX_AUTH_AGE_SECONDS = 24 * 3600


@dataclass(frozen=True, slots=True)
class TelegramIdentity:
    id: int
    username: str | None


class InvalidAuth(Exception):
    pass


def verify_webapp_init_data(
    init_data: str, bot_token: str, now: float | None = None
) -> TelegramIdentity:
    """Validate Mini App initData: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app"""
    try:
        fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError as exc:
        raise InvalidAuth("malformed init data") from exc
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    _verify(fields, secret, now)
    try:
        user = json.loads(fields["user"])
        return TelegramIdentity(int(user["id"]), user.get("username"))
    except (KeyError, ValueError, TypeError) as exc:
        raise InvalidAuth("init data has no user") from exc


def verify_login_widget(
    data: dict[str, str | int], bot_token: str, now: float | None = None
) -> TelegramIdentity:
    """Validate Login Widget data: https://core.telegram.org/widgets/login#checking-authorization"""
    fields = {key: str(value) for key, value in data.items()}
    secret = hashlib.sha256(bot_token.encode()).digest()
    _verify(fields, secret, now)
    try:
        return TelegramIdentity(int(fields["id"]), fields.get("username"))
    except (KeyError, ValueError) as exc:
        raise InvalidAuth("login data has no id") from exc


def _verify(fields: dict[str, str], secret: bytes, now: float | None) -> None:
    received = fields.get("hash")
    if not received:
        raise InvalidAuth("missing hash")
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()) if k != "hash")
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise InvalidAuth("bad hash")
    try:
        auth_date = int(fields["auth_date"])
    except (KeyError, ValueError) as exc:
        raise InvalidAuth("missing auth_date") from exc
    if (now or time.time()) - auth_date > MAX_AUTH_AGE_SECONDS:
        raise InvalidAuth("auth data expired")


def issue_token(user_id: int, secret: str) -> str:
    exp = int(time.time() + TOKEN_TTL.total_seconds())
    return jwt.encode({"sub": str(user_id), "exp": exp}, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> int:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp"]})
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise InvalidAuth("invalid token") from exc
