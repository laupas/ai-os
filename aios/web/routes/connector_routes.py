import re

from aiohttp import web

from aios.agents.agent_catalog import AgentCatalog
from aios.connectors.code_connector_manifest import CodeConnectorManifest
from aios.connectors.code_connectors import CODE_KEY, SETTINGS_KEY, CodeConnectors
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
from aios.variables.secret_extractor import SecretExtractor
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
        secrets: SecretExtractor | None = None,
        code: CodeConnectors | None = None,
    ) -> None:
        self._code = code
        self._secrets = secrets
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
            "description": "ai-os's own tools: data, messages, approvals, logs.",
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
        return web.json_response({"connectors": rows, "library": self._library()})

    async def _create(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, ConnectorRequest)
        name = body.name or ""
        if not NAME.match(name) or name == ConnectorCatalog.BUILTIN:
            raise web.HTTPBadRequest(text="a name is lower-case letters, digits, - and _")
        if self._connectors.get(name) is not None:
            raise web.HTTPConflict(text=f"there is already a connector called {name}")
        connector, moved = await self._without_secrets(self._connector(name, body, None), caller)
        manifest = self._manifest(connector)
        if CodeConnectors.is_code(connector) and manifest is None:
            raise web.HTTPBadRequest(text="there is no code connector of that name")
        connector = await self._connectors.put(connector)
        added = await self._add_agents(manifest) if manifest else []
        row = {**self._row(connector, caller), "moved_secrets": moved, "added_agents": added}
        return web.json_response(row, status=201)

    async def _save(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        existing = self._existing(request)
        body = await RequestBody.parse(request, ConnectorRequest)
        connector, moved = await self._without_secrets(
            self._unfixed(self._connector(existing.id, body, existing)), caller
        )
        connector = await self._connectors.put(connector)
        return web.json_response({**self._row(connector, caller), "moved_secrets": moved})

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

    async def _without_secrets(
        self, connector: Connector, caller: WebCaller
    ) -> tuple[Connector, list[str]]:
        """A literal secret in the config becomes an encrypted variable: the config
        is a git repository."""
        if self._secrets is None:
            return connector, []
        config, moved = await self._secrets.extract(
            connector.id, connector.config, caller.user.name
        )
        return connector.model_copy(update={"config": config}), moved

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

    def _manifest(self, connector: Connector) -> CodeConnectorManifest | None:
        return self._code.manifest_of(connector) if self._code else None

    def _library(self) -> list[dict]:
        if self._code is None:
            return []
        return [
            {
                "name": m.name,
                "description": m.description,
                "agents": [a.id for a in CodeConnectors.agents_of(m)],
            }
            for m in self._code.library.all()
        ]

    async def _add_agents(self, manifest: CodeConnectorManifest) -> list[str]:
        """The agents a code connector brings, those not there yet; an agent of the
        same name is the administrator's and is left alone."""
        added = []
        for agent in CodeConnectors.agents_of(manifest):
            if self._agents.get(agent.id) is None:
                await self._agents.save(agent)
                added.append(agent.id)
        return added

    def _unfixed(self, connector: Connector) -> Connector:
        """Settings aios.yaml fixes are not stored on the connector: they would be
        shadowed now and silently apply the day the line in aios.yaml is removed."""
        if self._code is None or not CodeConnectors.is_code(connector):
            return connector
        fixed = self._code.fixed(connector)
        settings = connector.config.get(SETTINGS_KEY) or {}
        kept = {k: v for k, v in settings.items() if k not in fixed}
        return connector.model_copy(update={"config": {**connector.config, SETTINGS_KEY: kept}})

    def _code_part(self, connector: Connector) -> dict | None:
        """For a code connector: what it is, its settings' schema, what is set on
        it, what aios.yaml fixes, and what applies."""
        if self._code is None or not CodeConnectors.is_code(connector):
            return None
        manifest = self._manifest(connector)
        return {
            "name": connector.config.get(CODE_KEY),
            "found": manifest is not None,
            "description": manifest.description if manifest else "",
            "schema": manifest.settings if manifest else {},
            "settings": connector.config.get(SETTINGS_KEY) or {},
            "fixed": self._code.fixed(connector),
            "effective": self._code.settings(connector),
        }

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
            "missing_variables": self._missing(connector),
            "code": self._code_part(connector),
        }

    def _missing(self, connector: Connector) -> list[str]:
        if self._resolver is None:
            return []
        manifest = self._manifest(connector)
        return self._resolver.missing(manifest.env if manifest else connector.config)

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
