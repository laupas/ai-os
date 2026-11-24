from aios.config.web_auth_config import WebAuthConfig
from aios.entities.users.user import User
from aios.web.login.new_user_maker import NewUserMaker


class NewUserPolicy:
    """Behind a login proxy with `create_users`: an address the proxy vouches for,
    in one of `domains`, that nobody has yet becomes a user in `group`."""

    def __init__(self, maker: NewUserMaker, group: str, domains: list[str], source: str) -> None:
        self._maker = maker
        self._group = group
        self._domains = domains
        self._source = source

    @classmethod
    def of(cls, auth: WebAuthConfig, maker: NewUserMaker) -> "NewUserPolicy | None":
        if not auth.create_users:
            return None
        return cls(maker, auth.default_group, auth.domains, auth.mode)

    async def user_for(self, email: str) -> User | None:
        domain = email.rsplit("@", 1)[-1].casefold() if "@" in email else ""
        if domain not in self._domains:
            return None
        try:
            return await self._maker.make(email, None, self._group, self._source)
        except ValueError:
            return None
