import re

from aiohttp import web

from aios.agents.agent_catalog import AgentCatalog
from aios.connectors.connector_authorizer import ConnectorAuthorizer
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.connectors.connector_probe import ConnectorProbe
from aios.connectors.connector_status_board import ConnectorStatusBoard
from aios.connectors.connector_tokens import ConnectorTokens
from aios.entities.connectors.connector import Connector
from aios.entities.connectors.connector_token import ConnectorToken
from aios.entities.connectors.sign_in_mode import SignInMode
from aios.entities.users.permission import Permission
from aios.storage.collection import Collection
from aios.variables.variable_resolver import VariableResolver
from aios.web.connector_request import ConnectorRequest
from aios.web.request_body import RequestBody
from aios.web.web_auth import WebAuth
from aios.web.web_caller import WebCaller
from aios.web.web_routes import WebRoutes

NAME = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")


class ConnectorRoutes(WebRoutes):
    """The MCP servers agents can be granted. Administrators only, except the list:
    anyone who may chat sees the connectors they can sign in to, with their own
    sign-in and, for a shared one, who signed it in; never a token, a config or
    somebody else's sign-in.

    A change applies to the next turn. The built-in `aios` server is listed but
    cannot be changed. Which agent may use a connector is set on the agent.
    """

    def __init__(
        self,
        connectors: Collection[Connector],
        catalog: ConnectorCatalog,
        board: ConnectorStatusBoard,
        agents: AgentCatalog,
        authorizer: ConnectorAuthorizer | None = None,
        tokens: ConnectorTokens | None = None,
        resolver: VariableResolver | None = None,
        probe: ConnectorProbe | None = None,
    ) -> None:
        self._probe = probe
        self._resolver = resolver
        self._authorizer = authorizer
        self._tokens = tokens
        self._connectors = connectors
        self._catalog = catalog
        self._board = board
        self._agents = agents

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/connectors", self._list)
        app.router.add_post("/api/connectors", self._create)
        app.router.add_put("/api/connectors/{name}", self._save)
        app.router.add_delete("/api/connectors/{name}", self._delete)
        app.router.add_post("/api/connectors/{name}/start", self._start)

    async def _list(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.CHAT)
        if not caller.can(Permission.ADMINISTER):
            rows = [
                self._member_row(c, caller)
                for c in self._catalog.all()
                if c.enabled and self._sign_in(c, caller) is not None
            ]
            return web.json_response({"connectors": rows})
        builtin = {
            "id": ConnectorCatalog.BUILTIN,
            "description": "ai-os's own tools: data, messages, approvals, crypto, logs.",
            "config": None,
            "enabled": True,
            "builtin": True,
            "status": "built in",
            "tools": self._catalog.builtin_tools(),
            "seen_at": None,
        }
        rows = [builtin, *(self._row(c, caller) for c in self._catalog.all())]
        agents = self._agents.all()
        for row in rows:
            row["used_by"] = [a.name for a in agents if row["id"] in a.connectors]
        return web.json_response({"connectors": rows})

    async def _create(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, ConnectorRequest)
        name = body.name or ""
        if not NAME.match(name) or name == ConnectorCatalog.BUILTIN:
            raise web.HTTPBadRequest(text="a name is lower-case letters, digits, - and _")
        if self._connectors.get(name) is not None:
            raise web.HTTPConflict(text=f"there is already a connector called {name}")
        connector = await self._connectors.put(self._connector(name, body, None))
        return web.json_response(self._row(connector, caller), status=201)

    async def _save(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        existing = self._existing(request)
        body = await RequestBody.parse(request, ConnectorRequest)
        connector = await self._connectors.put(self._connector(existing.id, body, existing))
        return web.json_response(self._row(connector, caller))

    async def _delete(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        await self._connectors.delete(self._existing(request).id)
        return web.json_response({"ok": True})

    async def _start(self, request: web.Request) -> web.Response:
        """Starts the connector on its own, as a turn would, and says how it went."""
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        connector = self._existing(request)
        if self._probe is None:
            raise web.HTTPServiceUnavailable(text="starting a connector is not available here")
        result = await self._probe.probe(connector.id, caller.user)
        return web.json_response(result.model_dump())

    @staticmethod
    def _connector(name: str, body: ConnectorRequest, existing: Connector | None) -> Connector:
        return Connector(
            id=name,
            description=body.description,
            config=body.config,
            enabled=body.enabled,
            sign_in=body.sign_in or (existing.sign_in if existing else SignInMode.SHARED),
            shared_fallback=body.shared_fallback
            if body.shared_fallback is not None
            else bool(existing and existing.shared_fallback),
        )

    def _member_row(self, connector: Connector, caller: WebCaller) -> dict:
        """What somebody who is not an administrator sees of a connector."""
        return {
            "id": connector.id,
            "description": connector.description,
            "config": None,
            "enabled": True,
            "builtin": False,
            "status": None,
            "tools": [],
            "seen_at": None,
            "used_by": [],
            "sign_in": self._sign_in(connector, caller),
        }

    def _row(self, connector: Connector, caller: WebCaller) -> dict:
        status = self._board.get(connector.id)
        return {
            **connector.model_dump(mode="json"),
            "builtin": False,
            "status": status.status if status else None,
            "error": status.error if status else None,
            "tools": status.tools if status else [],
            "seen_at": status.seen_at.isoformat() if status else None,
            # The entity's `sign_in` field is replaced by the state below; the mode
            # itself is kept here for the edit form.
            "sign_in_mode": connector.sign_in.value,
            "sign_in": self._sign_in(connector, caller),
            # Referred to as ${NAME} but set neither in the console nor the environment.
            "missing_variables": self._resolver.missing(connector.config) if self._resolver else [],
        }

    def _sign_in(self, connector: Connector, caller: WebCaller) -> dict | None:
        """Whether it can be signed in to, and how: the caller's own sign-in for a
        per-user connector, the shared one where it is used (and always for an
        administrator), and how many users signed in (administrators only). Never a
        token, and never another user's sign-in."""
        if self._authorizer is None or self._authorizer.url_of(connector.id) is None:
            return None
        admin = caller.can(Permission.ADMINISTER)
        per_user = connector.sign_in is SignInMode.PER_USER
        tokens = self._tokens
        mine = tokens.of_user(connector.id, caller.user.id) if tokens and per_user else None
        shared = tokens.shared(connector.id) if tokens else None
        show_shared = admin or not per_user or connector.shared_fallback
        return {
            "mode": connector.sign_in.value,
            "shared_fallback": connector.shared_fallback,
            "mine": self._state(mine) if per_user else None,
            "shared": self._state(shared) if show_shared else None,
            "users": tokens.users_signed_in(connector.id) if tokens and admin else None,
        }

    @staticmethod
    def _state(token: ConnectorToken | None) -> dict:
        return {
            "signed_in": token is not None,
            "by": token.signed_in_by if token else None,
            "at": token.signed_in_at.isoformat() if token and token.signed_in_at else None,
            "expires_at": token.expires_at.isoformat() if token and token.expires_at else None,
            "renewable": bool(token and token.refresh_token),
        }

    def _existing(self, request: web.Request) -> Connector:
        name = request.match_info["name"]
        connector = self._connectors.get(name)
        if connector is None:
            if name == ConnectorCatalog.BUILTIN:
                raise web.HTTPConflict(text="the built-in aios connector cannot be changed")
            raise web.HTTPNotFound(text="no such connector")
        return connector
