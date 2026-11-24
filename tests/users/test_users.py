from aios.common.id_generator import IdGenerator
from aios.config.owner_config import OwnerConfig
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.permission import Permission
from aios.users.default_groups import DefaultGroups
from aios.users.owner_bootstrapper import OwnerBootstrapper
from tests.fakes.world import World


async def test_owner_has_every_permission_and_bob_none() -> None:
    world = await World().setup()
    assert world.authorizer.permissions_of(world.alice) == set(Permission)
    assert world.authorizer.permissions_of(world.bob) == set()
    assert not world.authorizer.has(None, Permission.CHAT)


async def test_an_unknown_group_grants_nothing() -> None:
    world = await World().setup()
    ghost = world.bob.model_copy(update={"group_ids": ["does-not-exist"]})
    assert world.authorizer.permissions_of(ghost) == set()


async def test_bootstrap_creates_groups_and_the_owner_with_their_accounts() -> None:
    world = World()
    owner = OwnerConfig(name="Alice", accounts=[ChannelAccount(channel="slack", address="U1")])
    await OwnerBootstrapper(world.users, world.groups, DefaultGroups(), owner, IdGenerator()).run()

    [created] = world.users.all()
    assert created.group_ids == [DefaultGroups.OWNER]
    assert [a.channel for a in created.accounts] == ["slack"]
    assert {g.id for g in world.groups.all()} == {"owner", "member", "trusted_contact"}


async def test_bootstrap_never_touches_existing_data() -> None:
    world = await World().setup()
    owner = OwnerConfig(name="Someone else")
    await OwnerBootstrapper(world.users, world.groups, DefaultGroups(), owner, IdGenerator()).run()
    assert {u.name for u in world.users.all()} == {"Alice", "Bob"}


async def test_bootstrap_without_owner_config_creates_an_owner_who_can_sign_in() -> None:
    world = World()
    await OwnerBootstrapper(world.users, world.groups, DefaultGroups(), None, IdGenerator()).run()
    [created] = world.users.all()
    assert created.name == "Owner" and created.group_ids == [DefaultGroups.OWNER]
    assert created.account_for("web") is not None
