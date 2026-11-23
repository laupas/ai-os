from typing import Any

from aiohttp import web
from aiohttp.test_utils import TestServer


class WebhookTarget:
    """Somewhere to post to: keeps every request it got and answers `status`."""

    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.requests: list[dict[str, Any]] = []
        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", self._handle)
        self.server = TestServer(app)

    @property
    def url(self) -> str:
        return str(self.server.make_url("")).rstrip("/")

    async def _handle(self, request: web.Request) -> web.Response:
        self.requests.append(
            {
                "method": request.method,
                "path": request.path_qs,
                "headers": dict(request.headers),
                "body": await request.text(),
            }
        )
        return web.Response(status=self.status, text="received")
