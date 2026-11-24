import logging

from aios.bootstrap.startup_step import StartupStep
from aios.common.id_generator import IdGenerator
from aios.config.owner_config import OwnerConfig
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.group import Group
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.users.default_groups import DefaultGroups

log = logging.getLogger(__name__)


DEFAULT_OWNER = OwnerConfig(name="Owner", accounts=[ChannelAccount(channel="web", address="owner")])


class OwnerBootstrapper(StartupStep):
    """Makes a fresh data dir usable: default groups, and the owner from config.

    Without `owner` in the config the owner is "Owner" with a web account, so a
    fresh ai-os can be signed in to on the console's login page (`pick`, the
    default) and set up from there. Runs only while the collections are empty, so
    it never overwrites edits.
    """

    def __init__(
        self,
        users: Collection[User],
        groups: Collection[Group],
        default_groups: DefaultGroups,
        owner: OwnerConfig | None,
        ids: IdGenerator,
    ) -> None:
        self._users = users
        self._groups = groups
        self._default_groups = default_groups
        self._owner = owner
        self._ids = ids

    async def run(self) -> None:
        if self._groups.is_empty():
            for group in self._default_groups.all():
                await self._groups.put(group)
            log.info("created default groups")
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
            group_ids=[DefaultGroups.OWNER],
        )
        await self._users.put(owner)
        log.info("created owner %s", owner.name)
