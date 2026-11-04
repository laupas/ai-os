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

LOCAL_CLI_ACCOUNT = ChannelAccount(channel="cli", address="local")


class OwnerBootstrapper(StartupStep):
    """Makes a fresh data dir usable: default roles, and the owner from config.

    Runs only while the collections are empty, so it never overwrites edits.
    The owner always gets the local CLI account, since only someone with a shell
    on the host can use that channel.
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
        if self._owner is None:
            log.warning("no users and no `owner` in config: nobody can talk to ai-os yet")
            return
        accounts = list(self._owner.accounts)
        if not any(a.channel == LOCAL_CLI_ACCOUNT.channel for a in accounts):
            accounts.append(LOCAL_CLI_ACCOUNT)
        owner = User(
            id=self._ids.new_id(),
            name=self._owner.name,
            accounts=accounts,
            role_ids=[DefaultRoles.OWNER],
        )
        await self._users.put(owner)
        log.info("created owner %s", owner.name)
