import json

from aios.entities.users.permission import Permission
from tests.web.console import ALICE, BOB, Console


def text(data: dict) -> dict:
    return {"text": json.dumps(data)}


async def _put_user(c: Console, user, h) -> int:  # type: ignore[no-untyped-def]
    response = await c.client.put(
        f"/api/settings/users/{user.id}", json=text(user.model_dump()), headers=h
    )
    return response.status


async def test_a_member_of_a_group_has_its_roles_too(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        made = await c.client.post(
            "/api/settings/groups",
            json=text({"name": "Family", "role_ids": ["trusted_contact"]}),
            headers=h,
        )
        assert made.status == 201 and (await made.json())["id"] == "family"
        bob = c.world.users.get(c.world.bob.id)
        assert bob is not None
        assert not c.world.authorizer.has(bob, Permission.RECEIVE_UNAPPROVED)
        bob = bob.model_copy(update={"group_ids": ["family"]})
        assert await _put_user(c, bob, h) == 200
        assert c.world.authorizer.has(bob, Permission.RECEIVE_UNAPPROVED)
        assert c.world.authorizer.role_ids_of(bob) == ["member", "trusted_contact"]
        settings = await (await c.client.get("/api/settings", headers=h)).json()
        assert [g["id"] for g in settings["groups"]] == ["family"]


async def test_chat_through_a_group_is_enough_to_use_the_console(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        await c.client.post(
            "/api/settings/groups", json=text({"name": "Team", "role_ids": ["member"]}), headers=h
        )
        bob = c.world.users.get(c.world.bob.id)
        bob = bob.model_copy(update={"role_ids": [], "group_ids": ["team"]})  # type: ignore[union-attr]
        assert await _put_user(c, bob, h) == 200
        assert (await c.client.get("/api/conversations", headers=c.headers(BOB))).status == 200


async def test_unknown_groups_and_roles_are_refused(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        bad = await c.client.post(
            "/api/settings/groups", json=text({"name": "X", "role_ids": ["nope"]}), headers=h
        )
        assert bad.status == 400
        bob = c.world.users.get(c.world.bob.id)
        bob = bob.model_copy(update={"group_ids": ["nope"]})  # type: ignore[union-attr]
        assert await _put_user(c, bob, h) == 400


async def test_a_group_or_its_role_is_only_deleted_when_unused(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        await c.client.post(
            "/api/settings/roles",
            json=text({"name": "Readers", "permissions": ["chat"]}),
            headers=h,
        )
        await c.client.post(
            "/api/settings/groups", json=text({"name": "Club", "role_ids": ["readers"]}), headers=h
        )
        role_gone = await c.client.delete("/api/settings/roles/readers", headers=h)
        assert role_gone.status == 409 and "group Club" in await role_gone.text()
        bob = c.world.users.get(c.world.bob.id)
        bob = bob.model_copy(update={"group_ids": ["club"]})  # type: ignore[union-attr]
        await _put_user(c, bob, h)
        assert (await c.client.delete("/api/settings/groups/club", headers=h)).status == 409
        await _put_user(c, bob.model_copy(update={"group_ids": []}), h)
        assert (await c.client.delete("/api/settings/groups/club", headers=h)).status == 200


async def test_the_last_administrator_through_a_group_is_kept(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        await c.client.post(
            "/api/settings/groups", json=text({"name": "Admins", "role_ids": ["owner"]}), headers=h
        )
        alice = c.world.users.get(c.world.alice.id)
        alice = alice.model_copy(update={"role_ids": [], "group_ids": ["admins"]})  # type: ignore[union-attr]
        assert await _put_user(c, alice, h) == 200  # still an administrator, through the group
        emptied = await c.client.put(
            "/api/settings/groups/admins",
            json=text({"name": "Admins", "role_ids": []}),
            headers=h,
        )
        assert emptied.status == 409
