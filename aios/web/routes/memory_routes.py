from aiohttp import web

from aios.common.clock import Clock
from aios.common.id_generator import IdGenerator
from aios.entities.memories.memory import Memory
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.web.memory_request import MemoryRequest
from aios.web.request_body import RequestBody
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class MemoryRoutes(WebRoutes):
    """What ai-os remembers: list, add, edit, delete, each memory one user's or shared.
    Administrators only."""

    def __init__(
        self,
        memories: Collection[Memory],
        users: Collection[User],
        ids: IdGenerator,
        clock: Clock,
    ) -> None:
        self._memories = memories
        self._users = users
        self._ids = ids
        self._clock = clock

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/memories", self._list)
        app.router.add_post("/api/memories", self._create)
        app.router.add_put("/api/memories/{id}", self._update)
        app.router.add_delete("/api/memories/{id}", self._delete)

    async def _list(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        rows = sorted(self._memories.all(), key=lambda m: m.created_at, reverse=True)
        owners = sorted(self._users.all(), key=lambda u: u.name.lower())
        return web.json_response(
            {
                "memories": [m.model_dump(mode="json") for m in rows],
                "users": [{"id": u.id, "name": u.name} for u in owners],
            }
        )

    async def _create(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await self._body(request)
        memory = await self._memories.put(
            Memory(id=self._ids.new_id(), created_at=self._clock.now(), **body.model_dump())
        )
        return web.json_response(memory.model_dump(mode="json"), status=201)

    async def _update(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        memory = self._get(request)
        body = await self._body(request)
        updated = await self._memories.put(memory.model_copy(update=body.model_dump()))
        return web.json_response(updated.model_dump(mode="json"))

    async def _delete(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        await self._memories.delete(self._get(request).id)
        return web.json_response({"ok": True})

    def _get(self, request: web.Request) -> Memory:
        memory = self._memories.get(request.match_info["id"])
        if memory is None:
            raise web.HTTPNotFound(text="no such memory")
        return memory

    async def _body(self, request: web.Request) -> MemoryRequest:
        body = await RequestBody.parse(request, MemoryRequest)
        if body.user_id is not None and self._users.get(body.user_id) is None:
            raise web.HTTPBadRequest(text="no such user")
        return body
