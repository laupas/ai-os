from abc import abstractmethod

from aios.entities.users.user import User
from aios.web.login.web_login import WebLogin


class RedirectLogin(WebLogin):
    """A login that sends the browser to someone else to sign in (an identity
    provider) and gets it back with a code. `LoginRoutes` adds the two routes."""

    @abstractmethod
    async def start(self, provider: str, redirect_uri: str) -> tuple[str, str]:
        """Where to send the browser, and the `state` it will come back with."""

    @abstractmethod
    async def finish(self, state: str, code: str) -> User:
        """The user the provider signed in, or `LoginRefused`."""
