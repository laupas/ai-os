from aios.bootstrap.startup_step import StartupStep
from aios.config_repo.config_remote import ConfigRemote


class RemoteFromEnvironment(StartupStep):
    """After a restore from `AIOS_CONFIG_REMOTE`, makes that remote the console's,
    with auto-push, so the new machine keeps pushing where the old one did."""

    def __init__(
        self, remote: ConfigRemote, url: str | None, ssh_key: str | None, token: str | None
    ) -> None:
        self._remote = remote
        self._url = url
        self._ssh_key = ssh_key
        self._token = token

    async def run(self) -> None:
        if self._url:
            await self._remote.adopt(self._url, self._ssh_key, self._token)
