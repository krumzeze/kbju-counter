import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

BOT_TOKEN = "123456:test-token"


def sign_init_data(user_id: int, username: str = "tester", auth_date: int | None = None) -> str:
    fields = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAH",
        "user": json.dumps({"id": user_id, "first_name": "Test", "username": username}),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def sign_widget(user_id: int, auth_date: int | None = None) -> dict:
    fields = {"id": user_id, "first_name": "Test", "auth_date": auth_date or int(time.time())}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hashlib.sha256(BOT_TOKEN.encode()).digest()
    return {**fields, "hash": hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()}
