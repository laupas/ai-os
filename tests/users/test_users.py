from aios.common.id_generator import IdGenerator
from aios.config.owner_config import OwnerConfig
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.permission import Permission
from aios.users.default_roles import DefaultRoles
from aios.users.owner_bootstrapper import OwnerBootstrapper
from tests.fakes.world import World


async def test_owner_has_every_permission_and_bob_none() -> None:
    world = await World().setup()
    assert world.authorizer.permissions_of(world.alice) == set(Permission)
    assert world.authorizer.permissions_of(world.bob) == set()
    assert not world.authorizer.has(None, Permission.CHAT)


async def test_unknown_role_grants_nothing() -> None:
    world = await World().setup()
    ghost = world.bob.model_copy(update={"role_ids": ["does-not-exist"]})
    assert world.authorizer.permissions_of(ghost) == set()


async def test_bootstrap_creates_roles_and_the_owner_with_their_accounts() -> None:
    world = World()
    owner = OwnerConfig(name="Alice", accounts=[ChannelAccount(channel="slack", address="U1")])
    await OwnerBootstrapper(world.users, world.roles, DefaultRoles(), owner, IdGenerator()).run()

    [created] = world.users.all()
    assert created.role_ids == [DefaultRoles.OWNER]
    assert [a.channel for a in created.accounts] == ["slack"]
    assert {r.id for r in world.roles.all()} == {"owner", "member", "trusted_contact"}


async def test_bootstrap_never_touches_existing_data() -> None:
    world = await World().setup()
    owner = OwnerConfig(name="Someone else")
    await OwnerBootstrapper(world.users, world.roles, DefaultRoles(), owner, IdGenerator()).run()
    assert {u.name for u in world.users.all()} == {"Alice", "Bob"}


async def test_bootstrap_without_owner_config_creates_no_user() -> None:
    world = World()
    await OwnerBootstrapper(world.users, world.roles, DefaultRoles(), None, IdGenerator()).run()
    assert world.users.is_empty() and not world.roles.is_empty()
