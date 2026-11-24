import json

from aios.entities.users.group import Group
from aios.entities.users.permission import Permission
from aios.entities.users.role import Role
from aios.entities.users.user import User
from aios.users.groups_migration import GroupsMigration
from tests.config_repo.repo_world import RepoWorld
from tests.fakes.world import World
from tests.web.console import ALICE, BOB, Console


def text(data: dict) -> dict:
    return {"text": json.dumps(data)}


async def _put_user(c: Console, user, h) -> int:  # type: ignore[no-untyped-def]
    response = await c.client.put(
        f"/api/settings/users/{user.id}", json=text(user.model_dump()), headers=h
    )
    return response.status


async def test_a_member_of_a_group_has_its_permissions(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        made = await c.client.post(
            "/api/settings/groups",
            json=text({"name": "Family", "permissions": ["chat", "receive_unapproved"]}),
            headers=h,
        )
        assert made.status == 201 and (await made.json())["id"] == "family"
        bob = c.world.users.get(c.world.bob.id)
        assert bob is not None
        assert not c.world.authorizer.has(bob, Permission.RECEIVE_UNAPPROVED)
        bob = bob.model_copy(update={"group_ids": ["family"]})
        assert await _put_user(c, bob, h) == 200
        assert c.world.authorizer.has(bob, Permission.RECEIVE_UNAPPROVED)
        settings = await (await c.client.get("/api/settings", headers=h)).json()
        assert "family" in [g["id"] for g in settings["groups"]]
        assert "roles" not in settings


async def test_without_a_group_that_chats_nobody_gets_into_the_console(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        assert (await c.client.get("/api/conversations", headers=c.headers(BOB))).status == 200
        bob = c.world.users.get(c.world.bob.id)
        bob = bob.model_copy(update={"group_ids": ["trusted_contact"]})  # type: ignore[union-attr]
        assert await _put_user(c, bob, h) == 200
        assert (await c.client.get("/api/conversations", headers=c.headers(BOB))).status == 403


async def test_unknown_groups_and_the_built_in_everyone_are_refused(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        bob = c.world.users.get(c.world.bob.id)
        bob = bob.model_copy(update={"group_ids": ["nope"]})  # type: ignore[union-attr]
        assert await _put_user(c, bob, h) == 400
        everyone = await c.client.post(
            "/api/settings/groups", json=text({"name": "Everyone"}), headers=h
        )
        assert everyone.status == 409


async def test_a_group_is_only_deleted_when_nobody_is_in_it(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        await c.client.post("/api/settings/groups", json=text({"name": "Club"}), headers=h)
        bob = c.world.users.get(c.world.bob.id)
        bob = bob.model_copy(update={"group_ids": ["member", "club"]})  # type: ignore[union-attr]
        await _put_user(c, bob, h)
        assert (await c.client.delete("/api/settings/groups/club", headers=h)).status == 409
        await _put_user(c, bob.model_copy(update={"group_ids": ["member"]}), h)
        assert (await c.client.delete("/api/settings/groups/club", headers=h)).status == 200


async def test_nobody_can_lock_everyone_out(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        stripped = await c.client.put(
            "/api/settings/groups/owner",
            json=text({"name": "Administrators", "permissions": ["chat"]}),
            headers=h,
        )
        assert stripped.status == 409
        alice = c.world.users.get(c.world.alice.id)
        demoted = alice.model_copy(update={"group_ids": ["member"]})  # type: ignore[union-attr]
        assert await _put_user(c, demoted, h) == 409


async def test_roles_become_groups_of_the_same_id_once(tmp_path) -> None:
    w = RepoWorld(tmp_path)
    w.repo.init()
    world = World()
    groups = w._collection("groups", Group)  # type: ignore[attr-defined]
    await w.roles.put(Role(id="owner", name="Owner", permissions=set(Permission)))
    await w.roles.put(Role(id="family", name="Family", permissions={Permission.CHAT}))
    await groups.put(
        Group(id="club", name="Club", role_ids=["family"], permissions={Permission.APPROVE})
    )
    await world.users.put(User(id="a", name="A", role_ids=["owner"]))
    await world.users.put(User(id="b", name="B", role_ids=["family"], group_ids=["club"]))
    migration = GroupsMigration(w.store, world.users, w.roles, groups)
    await migration.run()
    assert w.roles.all() == []
    assert groups.get("owner").permissions == set(Permission)  # type: ignore[union-attr]
    assert groups.get("family").name == "Family"  # type: ignore[union-attr]
    club = groups.get("club")
    assert club is not None and club.role_ids == []
    assert club.permissions == {Permission.APPROVE, Permission.CHAT}
    assert world.users.get("a").group_ids == ["owner"]  # type: ignore[union-attr]
    b = world.users.get("b")
    assert b is not None and b.group_ids == ["club", "family"] and b.role_ids == []
    head = w.repo.log("groups/owner.yaml")
    await migration.run()  # nothing left to do
    assert w.repo.log("groups/owner.yaml") == head


async def test_agent_access_set_for_roles_moves_to_groups(tmp_path) -> None:
    from aios.web.aios_yaml_file import AiosYamlFile

    w = RepoWorld(tmp_path)
    w.repo.init()
    world = World()
    groups = w._collection("groups", Group)  # type: ignore[attr-defined]
    await w.roles.put(Role(id="member", name="Member", permissions={Permission.CHAT}))
    config = tmp_path / "aios.yaml"
    config.write_text("timezone: UTC\ncollection_access:\n  roles: read\n  users: write\n")
    await GroupsMigration(w.store, world.users, w.roles, groups, AiosYamlFile(config)).run()
    text = config.read_text()
    assert "groups: read" in text and "roles" not in text and "users: write" in text
