import asyncio
import logging

from aios.common.id_generator import IdGenerator
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.group import Group
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.storage.collection import Collection

log = logging.getLogger(__name__)

CHANNEL = "web"


class NewUserMaker:
    """Makes the user for an address a login vouched for and nobody has yet: a web
    account with that address, in the given group. One at a time, and never a second
    user for an address someone has: a browser's first visit sends several requests
    at once."""

    def __init__(
        self, users: Collection[User], groups: Collection[Group], ids: IdGenerator
    ) -> None:
        self._users = users
        self._groups = groups
        self._ids = ids
        self._lock = asyncio.Lock()

    def refusal(self, group_id: str) -> str | None:
        """Why users made this way may not be put in `group_id`, or None."""
        group = self._groups.get(group_id)
        if group is None:
            return f"there is no group {group_id}"
        if any(p.powerful for p in group.permissions):
            return f"group {group_id} administers ai-os; put new users in a group without that"
        if Permission.CHAT not in group.permissions:
            return f"group {group_id} cannot chat, so its members could not use the console"
        return None

    async def make(self, email: str, name: str | None, group_id: str, source: str) -> User:
        """The new user, or whoever has `email` already."""
        reason = self.refusal(group_id)
        if reason:
            raise ValueError(reason)
        async with self._lock:
            existing = self._owner_of(email)
            if existing is not None:
                return existing
            user = User(
                id=self._ids.new_id(),
                name=name.strip() if name and name.strip() else email.split("@")[0],
                accounts=[ChannelAccount(channel=CHANNEL, address=email)],
                group_ids=[group_id],
                notes=f"Made on their first sign-in with {source}.",
            )
            await self._users.put(user)
        log.info(
            "web: made user %s (%s, group %s) on a %s sign-in", user.id, email, group_id, source
        )
        return user

    def _owner_of(self, email: str) -> User | None:
        wanted = email.strip().casefold()
        return next(
            (
                u
                for u in self._users.all()
                if any(a.channel == CHANNEL and a.address.casefold() == wanted for a in u.accounts)
            ),
            None,
        )
