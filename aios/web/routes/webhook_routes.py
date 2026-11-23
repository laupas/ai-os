import re

from aiohttp import web
from pydantic import ValidationError

from aios.entities.users.permission import Permission
from aios.entities.webhooks.webhook_destination import WebhookDestination
from aios.messaging.webhook.webhook_poster import WebhookPoster
from aios.storage.collection import Collection
from aios.variables.secret_extractor import SecretExtractor
from aios.web.request_body import RequestBody
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes
from aios.web.webhook_request import WebhookRequest
from aios.web.webhook_test_request import WebhookTestRequest

NAME = re.compile(r"^[a-z][a-z0-9-]*$")


class WebhookRoutes(WebRoutes):
    """Webhook destinations: list, add, edit, delete, and test. Administrators only.

    A destination is a file in the configuration repository, read for every turn, so
    a change applies without a restart. A literal secret in a header goes through
    `SecretExtractor` like a connector's, into a Variable. A test really posts, with
    the destination as typed, so it can be tried before it is saved.
    """

    def __init__(
        self,
        destinations: Collection[WebhookDestination],
        poster: WebhookPoster,
        secrets: SecretExtractor | None,
    ) -> None:
        self._destinations = destinations
        self._poster = poster
        self._secrets = secrets

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/webhooks", self._list)
        app.router.add_post("/api/webhooks", self._create)
        app.router.add_post("/api/webhooks/test", self._test)
        app.router.add_put("/api/webhooks/{name}", self._save)
        app.router.add_delete("/api/webhooks/{name}", self._delete)

    async def _list(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        return web.json_response(
            {
                "enabled": self._poster.enabled,
                "destinations": [self._row(d) for d in self._destinations.all()],
            }
        )

    async def _create(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, WebhookRequest)
        if not body.name or not NAME.match(body.name):
            raise web.HTTPBadRequest(text="a name of lower-case letters, digits and dashes")
        if self._destinations.get(body.name) is not None:
            raise web.HTTPConflict(text=f"there is already a destination called {body.name}")
        return web.json_response(await self._store(body.name, body, caller.user.name), status=201)

    async def _save(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        name = self._existing(request)
        body = await RequestBody.parse(request, WebhookRequest)
        return web.json_response(await self._store(name, body, caller.user.name))

    async def _delete(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        await self._destinations.delete(self._existing(request))
        return web.json_response({"ok": True})

    async def _test(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, WebhookTestRequest)
        destination = self._destination(body.destination.name or "test", body.destination)
        result = await self._poster.post(destination, body.fields)
        return web.json_response(result.model_dump())

    async def _store(self, name: str, body: WebhookRequest, author: str) -> dict:
        destination = self._destination(name, body)
        if self._secrets is not None:
            extracted, _ = await self._secrets.extract(
                name, {"headers": destination.headers}, author, kind="webhook"
            )
            destination = destination.model_copy(update={"headers": extracted["headers"]})
        return self._row(await self._destinations.put(destination))

    @staticmethod
    def _destination(name: str, body: WebhookRequest) -> WebhookDestination:
        try:
            return WebhookDestination(id=name, **body.model_dump(exclude={"name"}))
        except ValidationError as exc:
            problems = "; ".join(e["msg"].removeprefix("Value error, ") for e in exc.errors())
            raise web.HTTPBadRequest(text=problems) from exc

    def _row(self, destination: WebhookDestination) -> dict:
        return {
            **destination.model_dump(mode="json", exclude={"id"}),
            "name": destination.id,
            "missing": self._poster.missing(destination),
        }

    def _existing(self, request: web.Request) -> str:
        name = request.match_info["name"]
        if self._destinations.get(name) is None:
            raise web.HTTPNotFound(text="no such destination")
        return name
