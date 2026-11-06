import json

from tests.web.console import ALICE, Console


def text(data: dict) -> dict:
    return {"text": json.dumps(data)}


async def test_roles_are_created_described_and_only_deleted_when_unused(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        settings = await (await c.client.get("/api/settings", headers=h)).json()
        assert "console" in settings["permission_descriptions"]["administer"]
        r = await c.client.post(
            "/api/settings/roles", json=text({"name": "Family", "permissions": ["chat"]}), headers=h
        )
        assert r.status == 201 and (await r.json())["id"] == "family"
        again = await c.client.post(
            "/api/settings/roles", json=text({"name": "Family", "permissions": []}), headers=h
        )
        assert again.status == 409
        bob = c.world.bob.model_copy(update={"role_ids": ["family"]})
        assert (
            await c.client.put(
                f"/api/settings/users/{bob.id}", json=text(bob.model_dump()), headers=h
            )
        ).status == 200
        assert (
            await c.client.delete("/api/settings/roles/family", headers=h)
        ).status == 409  # in use
        bob = bob.model_copy(update={"role_ids": []})
        await c.client.put(f"/api/settings/users/{bob.id}", json=text(bob.model_dump()), headers=h)
        assert (await c.client.delete("/api/settings/roles/family", headers=h)).status == 200


async def test_nobody_can_lock_everyone_out(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        owner = c.world.roles.get("owner")
        assert owner is not None
        from aios.entities.users.permission import Permission

        stripped = owner.model_copy(update={"permissions": {Permission.CHAT}})
        r = await c.client.put(
            "/api/settings/roles/owner", json=text(stripped.model_dump(mode="json")), headers=h
        )
        assert r.status == 409
        alice = c.world.users.get(c.world.alice.id)
        demoted = alice.model_copy(update={"role_ids": ["member"]})  # type: ignore[union-attr]
        r = await c.client.put(
            f"/api/settings/users/{demoted.id}", json=text(demoted.model_dump()), headers=h
        )
        assert r.status == 409


async def test_a_user_cannot_get_a_role_that_does_not_exist(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        body = {
            "name": "Anna",
            "accounts": [{"channel": "signal", "address": "+41"}],
            "role_ids": ["nope"],
        }
        assert (
            await c.client.post("/api/settings/users", json=text(body), headers=h)
        ).status == 400
        body["role_ids"] = ["member"]
        assert (
            await c.client.post("/api/settings/users", json=text(body), headers=h)
        ).status == 201


async def test_a_key_from_the_reference_goes_into_the_text_keeping_its_comments(
    tmp_path,
) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        settings = await (await c.client.get("/api/settings", headers=h)).json()
        assert "AgentConfig" in settings["config_schema"]["$defs"]
        text = "# keep me\nchannels: [web]\n"
        r = await c.client.post(
            "/api/settings/config-insert",
            json={"text": text, "path": ["agent", "auth"], "value": "subscription"},
            headers=h,
        )
        inserted = (await r.json())["text"]
        assert inserted.startswith("# keep me\n") and "agent:\n  auth: subscription" in inserted
        assert c.config_file.read_text() == "channels: [web]\n"  # nothing saved
