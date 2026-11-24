from aios.common.id_generator import IdGenerator
from aios.entities.users.web_password import WebPassword
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.users.default_roles import DefaultRoles
from aios.users.owner_bootstrapper import OwnerBootstrapper
from aios.web.login.owner_password_seed import OwnerPasswordSeed
from aios.web.login.password_hasher import PasswordHasher
from aios.web.login.web_passwords import WebPasswords
from tests.fakes.world import World


def _passwords(world: World) -> WebPasswords:
    definition = CollectionDefinition(name="web-passwords", entity=WebPassword)
    return WebPasswords(Collection(definition, world.store), PasswordHasher(), world.clock)


async def _fresh() -> tuple[World, WebPasswords]:
    world = World()
    await OwnerBootstrapper(world.users, world.roles, DefaultRoles(), None, IdGenerator()).run()
    return world, _passwords(world)


async def test_a_fresh_owner_gets_the_password_from_the_environment() -> None:
    world, passwords = await _fresh()
    await OwnerPasswordSeed(world.users, passwords, "a long first password").run()
    [owner] = world.users.all()
    assert await passwords.verify(owner.id, "a long first password")


async def test_once_anyone_has_a_password_the_environment_changes_nothing() -> None:
    world, passwords = await _fresh()
    [owner] = world.users.all()
    await passwords.set(owner.id, "chosen in the console", "owner")
    await OwnerPasswordSeed(world.users, passwords, "a long first password").run()
    assert await passwords.verify(owner.id, "chosen in the console")


async def test_an_installation_with_more_users_is_left_alone() -> None:
    world = await World().setup()
    passwords = _passwords(world)
    await OwnerPasswordSeed(world.users, passwords, "a long first password").run()
    assert passwords.user_ids() == []


async def test_a_too_short_password_is_not_used(caplog) -> None:
    world, passwords = await _fresh()
    await OwnerPasswordSeed(world.users, passwords, "short").run()
    assert passwords.user_ids() == []
    assert "AIOS_OWNER_PASSWORD not used" in caplog.text
