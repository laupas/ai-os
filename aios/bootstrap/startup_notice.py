import logging
from datetime import datetime, timedelta
from pathlib import Path

from aios.channels.channel_directory import ChannelDirectory
from aios.common.clock import Clock
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.users.default_roles import DefaultRoles

log = logging.getLogger(__name__)

TEXT = ":large_green_circle: ai-os started and is ready."


class StartupNotice:
    """Tells the owners that ai-os has started, on every enabled channel that can
    open a conversation by itself and that the owner has an account on.

    A start within `quiet` of the last notice says nothing, so a crash loop does not
    post once per restart. The time of the last notice is kept in `marker`, a file
    in the data dir, because it has to outlive the process. Best effort throughout:
    a failure here is logged and never stops ai-os from starting.
    """

    def __init__(
        self,
        users: Collection[User],
        channels: ChannelDirectory,
        clock: Clock,
        marker: Path,
        quiet: timedelta = timedelta(minutes=10),
    ) -> None:
        self._users = users
        self._channels = channels
        self._clock = clock
        self._marker = marker
        self._quiet = quiet

    async def run(self) -> None:
        try:
            now = self._clock.now()
            last = self._last_notice()
            if last is not None and now - last < self._quiet:
                log.info("startup notice skipped: the last one was at %s", last)
                return
            self._marker.parent.mkdir(parents=True, exist_ok=True)
            self._marker.write_text(now.isoformat())
            await self._post()
        except Exception:
            log.exception("startup notice failed")

    async def _post(self) -> None:
        owners = self._users.filter(lambda u: DefaultRoles.OWNER in u.role_ids)
        for channel in self._channels.enabled():
            starter = self._channels.thread_starter_for(channel.name)
            if starter is None:
                continue
            for owner in owners:
                account = owner.account_for(channel.name)
                if account is None:
                    continue
                try:
                    await starter.start_thread(account.address, TEXT)
                except Exception:
                    log.exception("startup notice to %s on %s failed", owner.name, channel.name)

    def _last_notice(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self._marker.read_text().strip())
        except (FileNotFoundError, ValueError):
            return None
