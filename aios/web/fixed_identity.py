from aiohttp import web

from aios.web.web_identity import WebIdentity


class FixedIdentity(WebIdentity):
    """Every request is `email`. For running locally and for tests; with None,
    which is what an unconfigured console gets, every request is refused."""

    def __init__(self, email: str | None) -> None:
        self._email = email

    async def email_of(self, request: web.Request) -> str | None:
        return self._email
