import asyncio

from aiohttp import web
from pydantic import ValidationError

from aios.agents.agent_catalog import AgentCatalog
from aios.agents.agent_unavailable_error import AgentUnavailableError
from aios.common.clock import Clock
from aios.common.id_generator import IdGenerator
from aios.entities.schedules.schedule import Schedule
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.scheduler.schedule_runner import ScheduleRunner
from aios.scheduler.schedule_timing import ScheduleTiming
from aios.storage.collection import Collection
from aios.web.request_body import RequestBody
from aios.web.schedule_request import ScheduleRequest
from aios.web.schedule_update import ScheduleUpdate
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class ScheduleRoutes(WebRoutes):
    """Lists, creates, edits, switches, runs and deletes schedules. Administrators
    only. Every save goes through the `Schedule` model, so a bad cron expression,
    time zone or user is refused here rather than at the next tick.

    Changing when a cron schedule runs counts from now: otherwise moving 07:00 to
    06:00 would make today's 06:00, already past, due at once.
    """

    def __init__(
        self,
        schedules: Collection[Schedule],
        timing: ScheduleTiming,
        runner: ScheduleRunner,
        clock: Clock,
        ids: IdGenerator,
        users: Collection[User],
        agents: AgentCatalog,
    ) -> None:
        self._schedules = schedules
        self._timing = timing
        self._runner = runner
        self._clock = clock
        self._ids = ids
        self._users = users
        self._agents = agents
        self._tasks: set[asyncio.Task[None]] = set()

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/schedules", self._list)
        app.router.add_post("/api/schedules", self._create)
        app.router.add_put("/api/schedules/{id}", self._save)
        app.router.add_patch("/api/schedules/{id}", self._update)
        app.router.add_post("/api/schedules/{id}/run", self._run)
        app.router.add_delete("/api/schedules/{id}", self._delete)

    async def _list(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        now = self._clock.now()
        rows = []
        for schedule in sorted(self._schedules.all(), key=lambda s: s.name):
            upcoming = self._timing.next_after(schedule, now) if schedule.enabled else None
            rows.append(
                {
                    **schedule.model_dump(mode="json"),
                    "next_run": upcoming.isoformat() if upcoming else None,
                }
            )
        return web.json_response(
            {
                "schedules": rows,
                "users": [{"id": u.id, "name": u.name} for u in self._users.all()],
                "agents": [a.name for a in self._agents.delegates()],
            }
        )

    async def _create(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, ScheduleRequest)
        schedule = self._build(
            {**body.model_dump(), "id": self._ids.new_id(), "created_at": self._clock.now()}
        )
        await self._schedules.put(schedule)
        return web.json_response({"id": schedule.id}, status=201)

    async def _save(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        current = self._get(request)
        body = await RequestBody.parse(request, ScheduleRequest)
        fields = body.model_dump()
        if body.once_at is not None:
            fields["last_fired_at"] = None  # a one-off fires while this is unset
        elif body.cron != current.cron or body.timezone != current.timezone:
            fields["last_fired_at"] = self._clock.now()
        schedule = self._build({**current.model_dump(), **fields})
        await self._schedules.put(schedule)
        return web.json_response({"ok": True})

    def _build(self, data: dict[str, object]) -> Schedule:
        if self._users.get(str(data["user_id"])) is None:
            raise web.HTTPBadRequest(text="no such user")
        if data.get("agent") == AgentCatalog.ORCHESTRATOR:
            data = {**data, "agent": None}
        try:
            self._agents.main(data.get("agent"))  # type: ignore[arg-type]
        except AgentUnavailableError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        try:
            return Schedule.model_validate(data)
        except (ValueError, KeyError, ValidationError) as exc:  # KeyError: unknown zone
            raise web.HTTPBadRequest(text=str(exc)) from exc

    async def _update(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        schedule = self._get(request)
        body = await RequestBody.parse(request, ScheduleUpdate)
        await self._schedules.put(schedule.model_copy(update={"enabled": body.enabled}))
        return web.json_response({"ok": True})

    async def _run(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        task = asyncio.create_task(self._runner.run(self._get(request)))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return web.json_response({"ok": True}, status=202)

    async def _delete(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        await self._schedules.delete(self._get(request).id)
        return web.json_response({"ok": True})

    def _get(self, request: web.Request) -> Schedule:
        schedule = self._schedules.get(request.match_info["id"])
        if schedule is None:
            raise web.HTTPNotFound(text="no such schedule")
        return schedule
