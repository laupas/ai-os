from aiohttp import web

from aios.agents.agent_catalog import AgentCatalog
from aios.agents.catalog_error import CatalogError
from aios.agents.skill_catalog import SkillCatalog
from aios.entities.skills.skill import Skill
from aios.entities.users.permission import Permission
from aios.web.request_body import RequestBody
from aios.web.skill_request import SkillRequest
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class SkillRoutes(WebRoutes):
    """Skills: add, edit, delete. Administrators only. Which agent may use a skill
    is set on the agent; deleting a skill takes it off every agent.

    A change is a file in the configuration repository, which the CLI reads, so it
    applies to the next turn. The skills themselves are listed with the agents (`GET /api/agents`).
    """

    def __init__(self, skills: SkillCatalog, agents: AgentCatalog) -> None:
        self._skills = skills
        self._agents = agents

    def register(self, app: web.Application) -> None:
        app.router.add_post("/api/skills", self._create)
        app.router.add_put("/api/skills/{name}", self._save)
        app.router.add_delete("/api/skills/{name}", self._delete)

    async def _create(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, SkillRequest)
        if not body.name:
            raise web.HTTPBadRequest(text="a new skill needs a name")
        if self._skills.get(body.name) is not None:
            raise web.HTTPConflict(text=f"there is already a skill called {body.name}")
        return web.json_response(await self._store(body.name, body), status=201)

    async def _save(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        name = self._existing(request)
        return web.json_response(
            await self._store(name, await RequestBody.parse(request, SkillRequest))
        )

    async def _delete(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        name = self._existing(request)
        await self._skills.delete(name)
        for agent in self._agents.all():
            if name in agent.skills:
                skills = [s for s in agent.skills if s != name]
                await self._agents.save(agent.model_copy(update={"skills": skills}))
        return web.json_response({"ok": True})

    async def _store(self, name: str, body: SkillRequest) -> dict:
        try:
            skill = await self._skills.save(
                Skill(id=name, description=body.description, content=body.content)
            )
        except CatalogError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        return {**skill.model_dump(), "name": skill.id}

    def _existing(self, request: web.Request) -> str:
        name = request.match_info["name"]
        if self._skills.get(name) is None:
            raise web.HTTPNotFound(text="no such skill")
        return name
