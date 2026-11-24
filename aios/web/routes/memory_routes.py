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
from aios.web.web_caller import WebCaller
from aios.web.web_routes import WebRoutes


class MemoryRoutes(WebRoutes):
    """What ai-os remembers: list, add, edit, delete, each memory one user's or shared.

    Everyone who may chat sees their own memories and the shared ones, and writes
    their own; writing a shared one needs `manage_shared_memories`, since it goes
    into every user's turns. Administrators see and write everyone's."""

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
        caller = WebAuth.caller(request)
        visible = [m for m in self._memories.all() if self._may_read(caller, m)]
        rows = sorted(visible, key=lambda m: m.created_at, reverse=True)
        if caller.can(Permission.ADMINISTER):
            owners = sorted(self._users.all(), key=lambda u: u.name.lower())
        else:
            owners = [caller.user]
        return web.json_response(
            {
                "memories": [
                    {**m.model_dump(mode="json"), "editable": self._may_write(caller, m.user_id)}
                    for m in rows
                ],
                "users": [{"id": u.id, "name": u.name} for u in owners],
            }
        )

    async def _create(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        body = await self._body(request, caller)
        memory = await self._memories.put(
            Memory(id=self._ids.new_id(), created_at=self._clock.now(), **body.model_dump())
        )
        return web.json_response(memory.model_dump(mode="json"), status=201)

    async def _update(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        memory = self._get(request, caller)
        body = await self._body(request, caller)
        updated = await self._memories.put(memory.model_copy(update=body.model_dump()))
        return web.json_response(updated.model_dump(mode="json"))

    async def _delete(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        await self._memories.delete(self._get(request, caller).id)
        return web.json_response({"ok": True})

    @staticmethod
    def _may_read(caller: WebCaller, memory: Memory) -> bool:
        return memory.user_id in (None, caller.user.id) or caller.can(Permission.ADMINISTER)

    @staticmethod
    def _may_write(caller: WebCaller, user_id: str | None) -> bool:
        """Whether the caller may write a memory belonging to `user_id` (None: shared)."""
        if caller.can(Permission.ADMINISTER) or user_id == caller.user.id:
            return True
        return user_id is None and caller.can(Permission.MANAGE_SHARED_MEMORIES)

    def _get(self, request: web.Request, caller: WebCaller) -> Memory:
        memory = self._memories.get(request.match_info["id"])
        if memory is None or not self._may_read(caller, memory):
            raise web.HTTPNotFound(text="no such memory")
        if not self._may_write(caller, memory.user_id):
            raise web.HTTPForbidden(text="you may not change this memory")
        return memory

    async def _body(self, request: web.Request, caller: WebCaller) -> MemoryRequest:
        body = await RequestBody.parse(request, MemoryRequest)
        if body.user_id is not None and self._users.get(body.user_id) is None:
            raise web.HTTPBadRequest(text="no such user")
        if not self._may_write(caller, body.user_id):
            raise web.HTTPForbidden(
                text="a shared memory needs manage_shared_memories"
                if body.user_id is None
                else "only an administrator writes another user's memories"
            )
        return body
