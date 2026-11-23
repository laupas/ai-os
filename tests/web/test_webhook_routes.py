import json

from tests.messaging.webhook_target import WebhookTarget
from tests.web.console import ALICE, BOB, Console

DESTINATION = {
    "name": "n8n-alerts",
    "description": "Alerts flow in n8n.",
    "url": "https://n8n.example.com/webhook/alerts",
    "headers": {"Authorization": "Bearer literal-token", "X-Source": "ai-os"},
    "fields": {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    "body": {"message": "{{text}}"},
    "approval": "allow",
}


async def _create(c: Console, **overrides: object):  # type: ignore[no-untyped-def]
    return await c.client.post(
        "/api/webhooks", json={**DESTINATION, **overrides}, headers=c.headers(ALICE, write=True)
    )


async def test_a_destination_is_saved_with_its_secret_moved_into_a_variable(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await _create(c)
        assert response.status == 201
        stored = c.webhooks.get("n8n-alerts")
        assert stored is not None and stored.approval == "allow"
        assert stored.headers == {
            "Authorization": "${N8N_ALERTS_AUTHORIZATION}",
            "X-Source": "ai-os",
        }
        assert c.variable_resolver.value_of("N8N_ALERTS_AUTHORIZATION") == "Bearer literal-token"

        listed = await (await c.client.get("/api/webhooks", headers=c.headers(ALICE))).json()
        assert listed["enabled"] is True
        assert [d["name"] for d in listed["destinations"]] == ["n8n-alerts"]
        assert listed["destinations"][0]["missing"] == []


async def test_a_bad_destination_is_refused(tmp_path) -> None:
    async with Console(tmp_path) as c:
        assert (await _create(c, body={"message": "{{nope}}"})).status == 400
        assert (await _create(c, name="Bad Name")).status == 400
        assert (await _create(c)).status == 201
        assert (await _create(c)).status == 409
        assert (await c.client.get("/api/webhooks", headers=c.headers(BOB))).status == 403


async def test_a_destination_is_edited_and_deleted(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await _create(c)
        response = await c.client.put(
            "/api/webhooks/n8n-alerts",
            json={**DESTINATION, "headers": {}, "approval": "deny"},
            headers=c.headers(ALICE, write=True),
        )
        assert response.status == 200
        assert c.webhooks.get("n8n-alerts").approval == "deny"  # type: ignore[union-attr]
        deleted = await c.client.delete(
            "/api/webhooks/n8n-alerts", headers=c.headers(ALICE, write=True)
        )
        assert deleted.status == 200 and c.webhooks.get("n8n-alerts") is None


async def test_a_typed_destination_can_be_tested_before_it_is_saved(tmp_path) -> None:
    target = WebhookTarget()
    await target.server.start_server()
    try:
        async with Console(tmp_path) as c:
            response = await c.client.post(
                "/api/webhooks/test",
                json={
                    "destination": {**DESTINATION, "url": target.url + "/hook"},
                    "fields": {"text": "hello"},
                },
                headers=c.headers(ALICE, write=True),
            )
            assert await response.json() == {"ok": True, "detail": "200 received"}
            assert json.loads(target.requests[0]["body"]) == {"message": "hello"}
            assert c.webhooks.all() == []
    finally:
        await target.server.close()
