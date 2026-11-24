from collections.abc import Callable

from aiohttp import web

from aios.agents.agent_catalog import AgentCatalog
from aios.agents.catalog_error import CatalogError
from aios.agents.skill_catalog import SkillCatalog
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.connectors.connector_status_board import ConnectorStatusBoard
from aios.entities.agents.agent import Agent
from aios.entities.connectors.connector import Connector
from aios.entities.users.permission import Permission
from aios.web.agent_edit_scope import AgentEditScope
from aios.web.agent_request import AgentRequest
from aios.web.request_body import RequestBody
from aios.web.web_auth import WebAuth
from aios.web.web_caller import WebCaller
from aios.web.web_routes import WebRoutes


class AgentRoutes(WebRoutes):
    """Agents, with the skills and connectors they can be granted. For
    `manage_agents`, within what `AgentEditScope` allows; the list also for
    `manage_skills`, whose page shows which agents use a skill.

    A change applies to the next turn; no restart is needed.
    """

    def __init__(
        self,
        agents: AgentCatalog,
        skills: SkillCatalog,
        connectors: ConnectorCatalog,
        board: ConnectorStatusBoard,
        builtin_tools: Callable[[], list[str]],
        scope: AgentEditScope,
    ) -> None:
        self._agents = agents
        self._skills = skills
        self._connectors = connectors
        self._board = board
        self._builtin_tools = builtin_tools
        self._scope = scope

    def _settings_of(self, connector: Connector) -> dict:
        """A code connector's settings as they apply, and which of them are locked
        against agents: shown on the agent, changed on the connector."""
        code = self._connectors.code
        if code is None or not code.is_code(connector):
            return {}
        return {"settings": code.settings(connector), "locked": sorted(code.locked(connector))}

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/agents", self._list)
        app.router.add_post("/api/agents", self._create)
        app.router.add_put("/api/agents/{name}", self._save)
        app.router.add_delete("/api/agents/{name}", self._delete)

    async def _list(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller_any(request, Permission.MANAGE_AGENTS, Permission.MANAGE_SKILLS)
        agents = self._agents.all()
        reach = self._scope.connectors(caller)
        builtin = (
            [
                {
                    "name": ConnectorCatalog.BUILTIN,
                    "enabled": True,
                    "tools": self._connectors.builtin_tools(),
                }
            ]
            if reach is None
            else []
        )
        connectors = [
            *builtin,
            *(
                {
                    "name": c.id,
                    "enabled": c.enabled,
                    "tools": self._board.tools_of(c.id),
                    **self._settings_of(c),
                }
                for c in self._connectors.all()
                if reach is None or c.id in reach
            ),
        ]
        skills = [
            {
                "name": s.id,
                "description": s.description,
                "content": s.content,
                "agents": [a.id for a in agents if s.id in a.skills],
            }
            for s in self._skills.all()
        ]
        return web.json_response(
            {
                "agents": [self._row(a) for a in agents],
                "skills": skills,
                "connectors": connectors,
                "builtin_tools": self._builtin_tools() if reach is None else [],
                "groups": [{"id": g.id, "name": g.name} for g in self._scope.groups(caller)],
                "orchestrator": AgentCatalog.ORCHESTRATOR,
            }
        )

    async def _create(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.MANAGE_AGENTS)
        body = await RequestBody.parse(request, AgentRequest)
        if not body.name:
            raise web.HTTPBadRequest(text="a new agent needs a name")
        if self._agents.get(body.name) is not None:
            raise web.HTTPConflict(text=f"there is already an agent called {body.name}")
        fields = body.model_dump(exclude={"name"}, exclude_unset=True)
        agent = await self._store(
            caller, None, {"description": "", "prompt": "", **fields, "id": body.name}
        )
        return web.json_response(self._row(agent), status=201)

    async def _save(self, request: web.Request) -> web.Response:
        """Changes the fields the body names and keeps the rest."""
        caller = WebAuth.caller(request, Permission.MANAGE_AGENTS)
        current = self._existing(request)
        body = await RequestBody.parse(request, AgentRequest)
        fields = body.model_dump(exclude={"name"}, exclude_unset=True)
        agent = await self._store(caller, current, {**current.model_dump(), **fields})
        return web.json_response(self._row(agent))

    async def _delete(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.MANAGE_AGENTS)
        try:
            await self._agents.delete(self._existing(request).id)
        except CatalogError as exc:
            raise web.HTTPConflict(text=str(exc)) from exc
        return web.json_response({"ok": True})

    async def _store(self, caller: WebCaller, current: Agent | None, data: dict) -> Agent:
        unknown = set(data.get("builtin_tools") or []) - set(self._builtin_tools())
        if unknown:
            raise web.HTTPBadRequest(text=f"not enabled for ai-os: {', '.join(sorted(unknown))}")
        missing = set(data.get("skills") or []) - self._skills.names()
        if missing:
            raise web.HTTPBadRequest(text=f"no such skill: {', '.join(sorted(missing))}")
        try:
            agent = Agent.model_validate(data)
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        refusal = self._scope.refusal(caller, current, agent)
        if refusal:
            raise web.HTTPForbidden(text=refusal)
        try:
            return await self._agents.save(agent)
        except (CatalogError, ValueError) as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc

    def _row(self, agent: Agent) -> dict:
        return {
            **agent.model_dump(mode="json"),
            "name": agent.id,
            "fixed": self._agents.is_fixed(agent.id),
        }

    def _existing(self, request: web.Request) -> Agent:
        agent = self._agents.get(request.match_info["name"])
        if agent is None:
            raise web.HTTPNotFound(text="no such agent")
        return agent
