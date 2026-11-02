import pytest

from belok.services import errors
from tests.conftest import login, onboarded


def _raise(exc: Exception) -> Exception:
    try:
        raise exc
    except Exception as caught:
        return caught


def test_fingerprint_ignores_message_and_groups_by_type():
    first, message, detail = errors.describe(_raise(KeyError("a")))
    second, _, _ = errors.describe(_raise(KeyError("b")))
    other, _, _ = errors.describe(_raise(ValueError("a")))
    assert first == second != other
    assert message.startswith("KeyError: 'a'")
    assert "Traceback" in detail


def test_web_fingerprint_ignores_numbers():
    assert errors.web_fingerprint("item 12 missing") == errors.web_fingerprint("item 7 missing")


@pytest.mark.db
async def test_unhandled_api_error_is_recorded_and_alerted_once(client, bot):
    admin = await onboarded(client)

    async def boom():
        raise RuntimeError("kaboom")

    client.app.add_api_route("/api/boom", boom)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await client.get("/api/boom", headers=admin)

    async with client.app.state.sessionmaker() as session:
        [row] = await errors.recent(session)
    assert (row.source, row.count, row.path, row.user_id) == ("api", 2, "GET /api/boom", 1001)
    alerts = [text for chat, text in bot.sent if "kaboom" in text]
    assert len(alerts) == 1 and "Новая ошибка" in alerts[0]


@pytest.mark.db
async def test_client_errors_are_listed_and_resolved(client, bot):
    admin = await onboarded(client)
    user = await login(client, 1002)
    body = {"message": "TypeError: x is undefined", "stack": "at Today", "path": "/today"}
    assert (await client.post("/api/client-errors", json=body, headers=user)).status_code == 204
    assert (await client.post("/api/client-errors", json=body)).status_code == 204

    assert (await client.get("/api/admin/errors", headers=user)).status_code == 403
    [row] = (await client.get("/api/admin/errors", headers=admin)).json()
    assert (row["source"], row["count"], row["path"]) == ("web", 2, "/today")

    url = f"/api/admin/errors?fingerprint={row['fingerprint']}"
    assert (await client.delete(url, headers=admin)).status_code == 204
    assert (await client.get("/api/admin/errors", headers=admin)).json() == []


@pytest.mark.db
async def test_alerts_are_capped_per_hour(client, bot):
    await onboarded(client)
    async with client.app.state.sessionmaker() as session:
        for i in range(errors.MAX_ALERTS_PER_HOUR + 3):
            await errors.record(
                session, bot, source="bot", fingerprint=f"fp{i}", message=f"Error {i}"
            )
        assert len(await errors.recent(session)) == errors.MAX_ALERTS_PER_HOUR + 3
        alerted = [e for e in await errors.recent(session) if e.alerted_at is not None]
    assert len(alerted) == errors.MAX_ALERTS_PER_HOUR
    assert sum("Новая ошибка" in text for _, text in bot.sent) == errors.MAX_ALERTS_PER_HOUR
