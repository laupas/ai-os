from aiohttp import web

from aios.common.clock import Clock
from aios.common.id_generator import IdGenerator
from aios.engine.memory_prompt_section import MemoryPromptSection
from aios.entities.memories.memory import Memory
from aios.entities.memories.memory_source import MemorySource
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.web.memory_merge_request import MemoryMergeRequest
from aios.web.memory_request import MemoryRequest
from aios.web.request_body import RequestBody
from aios.web.web_auth import WebAuth
from aios.web.web_caller import WebCaller
from aios.web.web_routes import WebRoutes


class MemoryRoutes(WebRoutes):
    """What ai-os remembers: list, add, edit, merge, delete, each memory one user's or
    shared, and what of them goes into a user's turns.

    Everyone who may chat sees their own memories and the shared ones, and writes
    their own; writing a shared one needs `manage_shared_memories`, since it goes
    into every user's turns. Administrators see and write everyone's."""

    def __init__(
        self,
        memories: Collection[Memory],
        users: Collection[User],
        ids: IdGenerator,
        clock: Clock,
        section: MemoryPromptSection,
    ) -> None:
        self._memories = memories
        self._users = users
        self._ids = ids
        self._clock = clock
        self._section = section

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/memories", self._list)
        app.router.add_post("/api/memories", self._create)
        app.router.add_post("/api/memories/merge", self._merge)
        app.router.add_get("/api/memories/prompt", self._prompt)
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
        body = await self._body(request, caller, MemoryRequest)
        memory = await self._memories.put(
            Memory(
                id=self._ids.new_id(),
                created_at=self._clock.now(),
                source=self._source(caller),
                **body.model_dump(),
            )
        )
        return web.json_response(memory.model_dump(mode="json"), status=201)

    async def _update(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        memory = self._writable(request.match_info["id"], caller)
        body = await self._body(request, caller, MemoryRequest)
        updated = await self._memories.put(self._changed(memory, body, caller))
        return web.json_response(updated.model_dump(mode="json"))

    async def _merge(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        body = await self._body(request, caller, MemoryMergeRequest)
        ids = list(dict.fromkeys(body.ids))
        if len(ids) < 2:
            raise web.HTTPBadRequest(text="merging takes two memories or more")
        # Every one is checked before anything is written.
        kept, *merged = [self._writable(i, caller) for i in ids]
        fields = body.model_dump(exclude={"ids"})
        kept = kept.model_copy(update={"created_at": min(m.created_at for m in [kept, *merged])})
        result = await self._memories.put(
            self._changed(kept, MemoryRequest.model_validate(fields), caller)
        )
        for memory in merged:
            await self._memories.delete(memory.id)
        return web.json_response(result.model_dump(mode="json"))

    async def _prompt(self, request: web.Request) -> web.Response:
        """What a user's turns are told of the memories, before their message adds
        what it names."""
        caller = WebAuth.caller(request)
        user_id = request.query.get("user_id") or caller.user.id
        if user_id != caller.user.id and not caller.can(Permission.ADMINISTER):
            raise web.HTTPForbidden(text="only an administrator sees another user's prompt")
        user = self._users.get(user_id)
        if user is None:
            raise web.HTTPNotFound(text="no such user")
        return web.json_response({"text": "\n".join(self._section.lines(user)).strip()})

    async def _delete(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        await self._memories.delete(self._writable(request.match_info["id"], caller).id)
        return web.json_response({"ok": True})

    def _changed(self, memory: Memory, body: MemoryRequest, caller: WebCaller) -> Memory:
        return memory.model_copy(
            update={
                **body.model_dump(),
                "updated_at": self._clock.now(),
                "source": self._source(caller),
            }
        )

    @staticmethod
    def _source(caller: WebCaller) -> MemorySource:
        return MemorySource(channel="console", user_id=caller.user.id)

    @staticmethod
    def _may_read(caller: WebCaller, memory: Memory) -> bool:
        return memory.user_id in (None, caller.user.id) or caller.can(Permission.ADMINISTER)

    @staticmethod
    def _may_write(caller: WebCaller, user_id: str | None) -> bool:
        """Whether the caller may write a memory belonging to `user_id` (None: shared)."""
        if caller.can(Permission.ADMINISTER) or user_id == caller.user.id:
            return True
        return user_id is None and caller.can(Permission.MANAGE_SHARED_MEMORIES)

    def _writable(self, memory_id: str, caller: WebCaller) -> Memory:
        memory = self._memories.get(memory_id)
        if memory is None or not self._may_read(caller, memory):
            raise web.HTTPNotFound(text="no such memory")
        if not self._may_write(caller, memory.user_id):
            raise web.HTTPForbidden(text="you may not change this memory")
        return memory

    async def _body[R: MemoryRequest](
        self, request: web.Request, caller: WebCaller, model: type[R]
    ) -> R:
        body = await RequestBody.parse(request, model)
        if body.user_id is not None and self._users.get(body.user_id) is None:
            raise web.HTTPBadRequest(text="no such user")
        if not self._may_write(caller, body.user_id):
            raise web.HTTPForbidden(
                text="a shared memory needs manage_shared_memories"
                if body.user_id is None
                else "only an administrator writes another user's memories"
            )
        return body
