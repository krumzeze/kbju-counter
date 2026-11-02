from datetime import timedelta
from types import SimpleNamespace

import pytest

from belok.bot.handlers.payments import pre_checkout, refunded_payment, successful_payment
from belok.db.models import Payment, User
from belok.i18n import Language
from belok.services.stars import parse_plans, plan_for_payload
from belok.timeutil import utcnow
from tests.conftest import onboarded


def test_parse_plans_skips_malformed_items():
    plans = parse_plans("30:250, 90:600,broken,0:10,365:x")
    assert [(p.days, p.stars, p.payload) for p in plans] == [
        (30, 250, "stars:30:250"),
        (90, 600, "stars:90:600"),
    ]


def test_payload_must_match_current_price():
    plans = parse_plans("30:250")
    assert plan_for_payload(plans, "stars:30:250", 250) == plans[0]
    assert plan_for_payload(plans, "stars:30:200", 200) is None
    assert plan_for_payload(plans, "stars:30:250", 1) is None


class FakeQuery:
    def __init__(self, payload: str, amount: int, currency: str = "XTR") -> None:
        self.invoice_payload = payload
        self.total_amount = amount
        self.currency = currency
        self.result: tuple[bool, str | None] | None = None

    async def answer(self, ok: bool, error_message: str | None = None) -> None:
        self.result = (ok, error_message)


def paid(charge_id: str, payload: str = "stars:30:150", amount: int = 150) -> SimpleNamespace:
    payment = SimpleNamespace(
        currency="XTR",
        total_amount=amount,
        invoice_payload=payload,
        telegram_payment_charge_id=charge_id,
    )
    return SimpleNamespace(successful_payment=payment)


def refunded(charge_id: str) -> SimpleNamespace:
    return SimpleNamespace(refunded_payment=SimpleNamespace(telegram_payment_charge_id=charge_id))


@pytest.mark.db
async def test_invoice_endpoint_uses_configured_price(client, bot):
    headers = await onboarded(client)
    response = await client.post("/api/payments/stars/90", headers=headers)
    assert response.json() == {"link": "https://t.me/$invoice"}
    invoice = bot.invoices[0]
    assert (invoice["currency"], invoice["payload"]) == ("XTR", "stars:90:375")
    assert invoice["prices"][0].amount == 375
    assert (await client.post("/api/payments/stars/7", headers=headers)).status_code == 404


@pytest.mark.db
async def test_pre_checkout_rejects_stale_price(client, settings):
    await onboarded(client)
    async with client.app.state.sessionmaker() as session:
        good, stale = FakeQuery("stars:30:150", 150), FakeQuery("stars:30:100", 100)
        await pre_checkout(good, session, settings, Language.RU)
        await pre_checkout(stale, session, settings, Language.RU)
    assert good.result == (True, None)
    assert stale.result[0] is False


@pytest.mark.db
async def test_stars_payment_extends_access_once_and_refunds(client, settings, bot):
    await onboarded(client)

    async def run(handler, message):
        async with client.app.state.sessionmaker() as session:
            user = await session.get(User, 1001)
            if handler is successful_payment:
                await handler(message, bot, session, user, settings)
            else:
                await handler(message, bot, session, user)
            await session.commit()
            return user.subscription_until

    first = await run(successful_payment, paid("c1"))
    assert first > utcnow() + timedelta(days=29)
    assert await run(successful_payment, paid("c1")) == first
    async with client.app.state.sessionmaker() as session:
        payment = await session.get(Payment, 1)
        assert (payment.provider, payment.amount, payment.currency) == ("stars", 150, "XTR")

    assert await run(refunded_payment, refunded("c1")) == first - timedelta(days=30)
    assert sum("✅" in text for chat, text in bot.sent if chat == 1001) == 1
