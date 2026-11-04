from abc import ABC, abstractmethod

from aiohttp import web


class WebRoutes(ABC):
    """One area of the console's API. A new area is a class plus one registration
    in `WebContainer`."""

    @abstractmethod
    def register(self, app: web.Application) -> None: ...
