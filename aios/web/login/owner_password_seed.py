import logging

from aios.bootstrap.startup_step import StartupStep
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.users.default_groups import DefaultGroups
from aios.web.login.web_passwords import WebPasswords

log = logging.getLogger(__name__)


class OwnerPasswordSeed(StartupStep):
    """Gives a fresh installation's owner a first console password from
    `AIOS_OWNER_PASSWORD`, so a one-shot deployment can start with
    `web.auth.mode: password` and nobody else can sign in first.

    Only while the owner is the only user and nobody has a password: once the
    console has passwords, they are its own and the variable changes nothing.
    """

    def __init__(
        self, users: Collection[User], passwords: WebPasswords, password: str | None
    ) -> None:
        self._users = users
        self._passwords = passwords
        self._password = password

    async def run(self) -> None:
        if not self._password or self._passwords.user_ids():
            return
        users = self._users.all()
        if len(users) != 1 or DefaultGroups.OWNER not in users[0].group_ids:
            return
        try:
            await self._passwords.set(users[0].id, self._password, "AIOS_OWNER_PASSWORD")
        except ValueError as error:
            log.error("AIOS_OWNER_PASSWORD not used: %s", error)
            return
        log.info("set the console password of %s from AIOS_OWNER_PASSWORD", users[0].name)
