import asyncio
import logging

from aios.common.id_generator import IdGenerator
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.permission import Permission
from aios.entities.users.role import Role
from aios.entities.users.user import User
from aios.storage.collection import Collection

log = logging.getLogger(__name__)

CHANNEL = "web"


class NewUserMaker:
    """Makes the user for an address a login vouched for and nobody has yet: a web
    account with that address and the given role. One at a time, and never a second
    user for an address someone has: a browser's first visit sends several requests
    at once."""

    def __init__(self, users: Collection[User], roles: Collection[Role], ids: IdGenerator) -> None:
        self._users = users
        self._roles = roles
        self._ids = ids
        self._lock = asyncio.Lock()

    def refusal(self, role_id: str) -> str | None:
        """Why `role_id` may not be given to users made this way, or None."""
        role = self._roles.get(role_id)
        if role is None:
            return f"there is no role {role_id}"
        if Permission.ADMINISTER in role.permissions or Permission.MANAGE_USERS in role.permissions:
            return f"role {role_id} administers ai-os; give new users a role without that"
        if Permission.CHAT not in role.permissions:
            return f"role {role_id} cannot chat, so its users could not use the console"
        return None

    async def make(self, email: str, name: str | None, role_id: str, source: str) -> User:
        """The new user, or whoever has `email` already."""
        reason = self.refusal(role_id)
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
                role_ids=[role_id],
                notes=f"Made on their first sign-in with {source}.",
            )
            await self._users.put(user)
        log.info("web: made user %s (%s, role %s) on a %s sign-in", user.id, email, role_id, source)
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
