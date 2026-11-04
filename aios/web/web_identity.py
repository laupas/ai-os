from abc import ABC, abstractmethod

from aiohttp import web


class WebIdentity(ABC):
    """Who sent a request, as an email address, or None when it cannot be told."""

    @abstractmethod
    async def email_of(self, request: web.Request) -> str | None: ...
