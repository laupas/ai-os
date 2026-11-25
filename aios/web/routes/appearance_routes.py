from aiohttp import web

from aios.entities.users.appearance import Appearance
from aios.storage.collection import Collection
from aios.web.appearance_request import AppearanceRequest
from aios.web.request_body import RequestBody
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class AppearanceRoutes(WebRoutes):
    """Each user's look of the console (light or dark, colour theme), kept with their
    account so it follows them to every browser. Always the caller's own: nobody reads
    or sets anyone else's. `null` until they first choose."""

    def __init__(self, appearances: Collection[Appearance]) -> None:
        self._appearances = appearances

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/me/appearance", self._get)
        app.router.add_put("/api/me/appearance", self._set)

    async def _get(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        saved = self._appearances.get(caller.user.id)
        return web.json_response(self._shown(saved) if saved else None)

    async def _set(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        body = await RequestBody.parse(request, AppearanceRequest)
        saved = await self._appearances.put(Appearance(id=caller.user.id, **body.model_dump()))
        return web.json_response(self._shown(saved))

    @staticmethod
    def _shown(appearance: Appearance) -> dict[str, str]:
        return appearance.model_dump(mode="json", exclude={"id"})
