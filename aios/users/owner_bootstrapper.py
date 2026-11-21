import logging

from aios.bootstrap.startup_step import StartupStep
from aios.common.id_generator import IdGenerator
from aios.config.owner_config import OwnerConfig
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.role import Role
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.users.default_roles import DefaultRoles

log = logging.getLogger(__name__)


DEFAULT_OWNER = OwnerConfig(name="Owner", accounts=[ChannelAccount(channel="web", address="owner")])


class OwnerBootstrapper(StartupStep):
    """Makes a fresh data dir usable: default roles, and the owner from config.

    Without `owner` in the config the owner is "Owner" with a web account, so a
    fresh ai-os can be signed in to on the console's login page (`pick`, the
    default) and set up from there. Runs only while the collections are empty, so
    it never overwrites edits.
    """

    def __init__(
        self,
        users: Collection[User],
        roles: Collection[Role],
        default_roles: DefaultRoles,
        owner: OwnerConfig | None,
        ids: IdGenerator,
    ) -> None:
        self._users = users
        self._roles = roles
        self._default_roles = default_roles
        self._owner = owner
        self._ids = ids

    async def run(self) -> None:
        if self._roles.is_empty():
            for role in self._default_roles.all():
                await self._roles.put(role)
            log.info("created default roles")
        if self._users.is_empty():
            await self._create_owner()

    async def _create_owner(self) -> None:
        config = self._owner or DEFAULT_OWNER
        if self._owner is None:
            log.warning("no users and no `owner` in config: created %s", DEFAULT_OWNER.name)
        owner = User(
            id=self._ids.new_id(),
            name=config.name,
            accounts=list(config.accounts),
            role_ids=[DefaultRoles.OWNER],
        )
        await self._users.put(owner)
        log.info("created owner %s", owner.name)
