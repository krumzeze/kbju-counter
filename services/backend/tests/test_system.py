import pytest
from sqlalchemy import select

from belok.db.models import AdminAction, LlmUsage, User
from belok.services import heartbeat
from belok.services.reminders import run_reminders
from belok.timeutil import local_today
from tests.conftest import onboarded
from tests.test_voice import FakeMessage, FakeStt, run_voice

pytestmark = pytest.mark.db

ADMIN, USER = 1001, 2002


async def disable(client, headers, key: str) -> list[dict]:
    response = await client.put(
        f"/api/admin/features/{key}", json={"enabled": False}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_features_are_on_by_default_and_admin_only(client):
    admin = await onboarded(client, ADMIN)
    user = await onboarded(client, USER)
    flags = (await client.get("/api/admin/features", headers=admin)).json()
    assert all(f["enabled"] for f in flags)
    assert {f["key"] for f in flags} >= {"photo", "text", "voice", "barcode", "reminders"}
    assert (await client.get("/api/admin/features", headers=user)).status_code == 403
    put = await client.put("/api/admin/features/photo", json={"enabled": False}, headers=user)
    assert put.status_code == 403
    assert (
        await client.put("/api/admin/features/nope", json={"enabled": False}, headers=admin)
    ).status_code == 422


async def test_disabled_feature_blocks_routes_and_is_logged(client):
    admin = await onboarded(client, ADMIN)
    user = await onboarded(client, USER)
    flags = await disable(client, admin, "text")
    assert {f["key"]: f["enabled"] for f in flags}["text"] is False
    me = (await client.get("/api/me", headers=user)).json()
    assert me["features"]["text"] is False and me["features"]["photo"] is True

    response = await client.post("/api/meals/text", json={"text": "гречка"}, headers=user)
    assert response.status_code == 503
    assert response.json()["detail"] == "feature_disabled"
    await disable(client, admin, "barcode")
    assert (await client.get("/api/barcode/4600000000000", headers=user)).status_code == 503

    async with client.app.state.sessionmaker() as session:
        action = await session.scalar(select(AdminAction))
    assert action.action == "set_feature"
    assert action.details == {"feature": "text", "old": True, "new": False}

    on = await client.put("/api/admin/features/text", json={"enabled": True}, headers=admin)
    assert on.status_code == 200
    ok = await client.post("/api/meals/text", json={"text": "гречка"}, headers=user)
    assert ok.status_code == 201


async def test_disabled_payments_hide_plans(client):
    admin = await onboarded(client, ADMIN)
    await disable(client, admin, "payments")
    assert (await client.get("/api/payments/plans", headers=admin)).json() == []


async def test_disabled_voice_in_bot(client, settings, analyzer):
    admin = await onboarded(client, ADMIN)
    await disable(client, admin, "voice")
    message = FakeMessage()
    await run_voice(client, settings, analyzer, FakeStt("гречка"), message)
    assert "недоступны" in message.answers[0]


async def test_disabled_reminders_still_beat(client, monkeypatch):
    admin = await onboarded(client, ADMIN)
    await disable(client, admin, "reminders")
    sent = []

    async def fake_send_due(*args) -> int:
        sent.append(args)
        return 0

    async def stop(_):
        raise RuntimeError("stop")

    monkeypatch.setattr("belok.services.reminders.send_due", fake_send_due)
    monkeypatch.setattr("belok.services.reminders.asyncio.sleep", stop)
    with pytest.raises(RuntimeError):
        await run_reminders(None, client.app.state.sessionmaker, None, None)
    assert sent == []
    health = (await client.get("/api/admin/health", headers=admin)).json()
    status = {c["key"]: c["status"] for c in health["checks"]}
    assert status["worker:reminders"] == "ok"


async def test_health_reports_each_service(client, settings):
    admin = await onboarded(client, ADMIN)
    settings.redis_url = "redis://127.0.0.1:1/0"
    async with client.app.state.sessionmaker() as session:
        await heartbeat.beat(session, "bot")
    response = await client.get("/api/admin/health", headers=admin)
    assert response.status_code == 200, response.text
    checks = {c["key"]: c for c in response.json()["checks"]}
    assert checks["database"]["status"] == "ok"
    assert checks["worker:bot"]["status"] == "ok"
    assert checks["worker:monitor"]["status"] == "fail"
    assert checks["redis"]["status"] == "fail"
    assert checks["telegram"] == {
        "key": "telegram",
        "status": "ok",
        "detail": "@belok_test_bot",
        "latency_ms": checks["telegram"]["latency_ms"],
    }
    assert checks["anthropic"]["status"] == "ok"
    assert checks["food_db"]["status"] == "ok"
    assert checks["stt"]["status"] == "off" and checks["stt"]["latency_ms"] is None
    assert checks["tribute"]["status"] == "off"
    user = await onboarded(client, USER)
    assert (await client.get("/api/admin/health", headers=user)).status_code == 403


async def test_health_warns_on_llm_error_rate(client, analyzer):
    admin = await onboarded(client, ADMIN)
    async with client.app.state.sessionmaker() as session:
        user = await session.get(User, ADMIN)
        for ok in (True, False, False, False, True):
            session.add(
                LlmUsage(
                    user_id=user.id,
                    day=local_today("UTC"),
                    kind="text",
                    model="m",
                    latency_ms=1,
                    ok=ok,
                )
            )
        await session.commit()
    checks = {
        c["key"]: c for c in (await client.get("/api/admin/health", headers=admin)).json()["checks"]
    }
    assert checks["anthropic"]["status"] == "warn"
    assert "3 из 5" in checks["anthropic"]["detail"]


async def test_failing_probe_is_reported_not_raised(client, analyzer):
    admin = await onboarded(client, ADMIN)

    async def broken() -> None:
        raise ConnectionError("no route")

    analyzer.ping = broken
    checks = {
        c["key"]: c for c in (await client.get("/api/admin/health", headers=admin)).json()["checks"]
    }
    assert checks["anthropic"]["status"] == "fail"
    assert checks["anthropic"]["detail"] == "ConnectionError: no route"
