from aiohttp import web

from aios.agents.catalog_error import CatalogError
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.entities.users.permission import Permission
from aios.entities.variables.variable import Variable
from aios.variables.variable_catalog import VariableCatalog
from aios.variables.variable_resolver import VariableResolver
from aios.web.request_body import RequestBody
from aios.web.variable_request import VariableRequest
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class VariableRoutes(WebRoutes):
    """Variables and secrets for connectors. Administrators only.

    A secret's value goes in and never comes back out: the list says that it is
    set, by whom and when. A change applies to the next turn.
    """

    def __init__(
        self,
        variables: VariableCatalog,
        resolver: VariableResolver,
        connectors: ConnectorCatalog,
    ) -> None:
        self._variables = variables
        self._resolver = resolver
        self._connectors = connectors

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/variables", self._list)
        app.router.add_post("/api/variables", self._create)
        app.router.add_put("/api/variables/{name}", self._save)
        app.router.add_delete("/api/variables/{name}", self._delete)

    async def _list(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        uses = {c.id: self._resolver.references(c.config) for c in self._connectors.all()}
        return web.json_response({"variables": [self._row(v, uses) for v in self._variables.all()]})

    async def _create(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, VariableRequest)
        if not body.name:
            raise web.HTTPBadRequest(text="a new variable needs a name")
        if self._variables.get(body.name) is not None:
            raise web.HTTPConflict(text=f"there is already a variable called {body.name}")
        await self._store(body.name, body, caller.user.name)
        return web.json_response({"ok": True}, status=201)

    async def _save(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        name = request.match_info["name"]
        if self._variables.get(name) is None:
            raise web.HTTPNotFound(text="no such variable")
        await self._store(name, await RequestBody.parse(request, VariableRequest), caller.user.name)
        return web.json_response({"ok": True})

    async def _delete(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        name = request.match_info["name"]
        if self._variables.get(name) is None:
            raise web.HTTPNotFound(text="no such variable")
        await self._variables.delete(name)
        self._resolver.forget(name)
        return web.json_response({"ok": True})

    async def _store(self, name: str, body: VariableRequest, author: str) -> None:
        try:
            await self._variables.save(
                name, body.value, body.secret, body.file, body.description, author
            )
        except CatalogError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc

    @staticmethod
    def _row(variable: Variable, uses: dict[str, set[str]]) -> dict:
        return {
            "name": variable.id,
            "secret": variable.secret,
            "file": variable.file,
            "description": variable.description,
            "value": None if variable.secret else variable.value,
            "updated_at": variable.updated_at.isoformat() if variable.updated_at else None,
            "updated_by": variable.updated_by,
            "used_by": sorted(c for c, names in uses.items() if variable.id in names),
        }
