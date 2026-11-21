from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.users.authorizer import Authorizer

CHANNEL = "web"


class ConsoleUsers:
    """The users who may sign in to the console: those with a `web` account and
    the `chat` permission."""

    def __init__(self, users: Collection[User], authorizer: Authorizer) -> None:
        self._users = users
        self._authorizer = authorizer

    def all(self) -> list[User]:
        return sorted(self._users.filter(self.may_sign_in), key=lambda u: u.name.casefold())

    def get(self, user_id: str) -> User | None:
        user = self._users.get(user_id)
        return user if user is not None and self.may_sign_in(user) else None

    def named(self, name: str) -> User | None:
        """The one user whose web address, name or alias is `name`; None when
        there is none, or more than one."""
        wanted = name.strip().casefold()
        found = [
            u
            for u in self.all()
            if u.matches_name(wanted)
            or any(a.channel == CHANNEL and a.address.casefold() == wanted for a in u.accounts)
        ]
        return found[0] if len(found) == 1 else None

    def may_sign_in(self, user: User) -> bool:
        return user.account_for(CHANNEL) is not None and self._authorizer.has(user, Permission.CHAT)

    @staticmethod
    def address_of(user: User) -> str | None:
        account = user.account_for(CHANNEL)
        return account.address if account else None
