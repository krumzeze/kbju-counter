import hashlib
import hmac
import json
from datetime import timedelta

import pytest

from belok.db.models import User
from belok.timeutil import utcnow
from tests.conftest import onboarded
from tests.test_tribute import FakeCatalog

pytestmark = pytest.mark.db

PRODUCTS = [
    {"id": 7, "webLink": "https://web.tribute.tg/p/IMK", "amount": 29900, "currency": "rub"},
    {"id": 8, "webLink": "https://web.tribute.tg/p/IMM", "amount": 74900, "currency": "rub"},
]


@pytest.fixture
def catalog(client) -> FakeCatalog:
    client.app.state.tribute = FakeCatalog(PRODUCTS)
    return client.app.state.tribute


def event(name: str, product_id: int, user_id: int = 1001, created_at: str = "t1") -> bytes:
    payload = {"product_id": product_id, "amount": 29900, "currency": "rub", "user_id": 5}
    payload["telegram_user_id"] = user_id
    return json.dumps({"name": name, "created_at": created_at, "payload": payload}).encode()


async def post(client, body: bytes, key: str = "key"):
    signature = hmac.new(key.encode(), body, hashlib.sha256).hexdigest()
    return await client.post(
        "/api/payments/tribute", content=body, headers={"trbt-signature": signature}
    )


async def access_until(client, user_id: int = 1001):
    async with client.app.state.sessionmaker() as session:
        user = await session.get(User, user_id)
        return user.subscription_until


async def test_plans_endpoint_lists_prices(client, catalog):
    headers = await onboarded(client)
    plans = (await client.get("/api/payments/plans", headers=headers)).json()
    assert [(p["code"], p["days"], p["amount"]) for p in plans] == [
        ("IMK", 30, 29900),
        ("IMM", 90, 74900),
    ]


async def test_purchase_extends_access_once(client, catalog, bot):
    await onboarded(client)
    body = event("new_digital_product", 7)
    assert (await post(client, body)).status_code == 200
    first = await access_until(client)
    assert first > utcnow() + timedelta(days=29)

    assert (await post(client, body)).status_code == 200
    assert await access_until(client) == first
    assert sum("✅" in text for chat, text in bot.sent if chat == 1001) == 1

    await post(client, event("new_digital_product", 8, created_at="t2"))
    assert await access_until(client) == first + timedelta(days=90)


async def test_refund_takes_days_back(client, catalog):
    await onboarded(client)
    await post(client, event("new_digital_product", 7))
    paid = await access_until(client)
    await post(client, event("digital_product_refund", 7, created_at="t9"))
    assert await access_until(client) == paid - timedelta(days=30)


async def test_bad_signature_and_unknown_product(client, catalog):
    await onboarded(client)
    assert (await post(client, event("new_digital_product", 7), key="wrong")).status_code == 401
    assert (await post(client, event("new_digital_product", 404))).status_code == 200
    assert await access_until(client) is None


async def test_webhook_disabled_without_key(client):
    response = await client.post("/api/payments/tribute", content=b"{}")
    assert response.status_code == 503
