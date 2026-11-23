import asyncio

from aiohttp import web
from pydantic import ValidationError

from aios.agents.agent_catalog import AgentCatalog
from aios.agents.agent_unavailable_error import AgentUnavailableError
from aios.common.clock import Clock
from aios.common.id_generator import IdGenerator
from aios.entities.triggers.trigger import Trigger
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.triggers.trigger_runner import TriggerRunner
from aios.triggers.trigger_timing import TriggerTiming
from aios.triggers.webhook_token import WebhookToken
from aios.web.request_body import RequestBody
from aios.web.trigger_request import TriggerRequest
from aios.web.trigger_update import TriggerUpdate
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class TriggerRoutes(WebRoutes):
    """Lists, creates, edits, switches, runs and deletes triggers. Administrators
    only. Every save goes through the `Trigger` model, so a bad cron expression,
    time zone or user is refused here rather than at the next tick.

    Changing when a cron trigger runs counts from now: otherwise moving 07:00 to
    06:00 would make today's 06:00, already past, due at once.

    A trigger's webhook token is made here and answered once, as `token`, when the
    webhook is turned on or renewed; the list shows only whether there is one.
    """

    def __init__(
        self,
        triggers: Collection[Trigger],
        timing: TriggerTiming,
        runner: TriggerRunner,
        clock: Clock,
        ids: IdGenerator,
        users: Collection[User],
        agents: AgentCatalog,
    ) -> None:
        self._triggers = triggers
        self._timing = timing
        self._runner = runner
        self._clock = clock
        self._ids = ids
        self._users = users
        self._agents = agents
        self._tasks: set[asyncio.Task[None]] = set()

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/triggers", self._list)
        app.router.add_post("/api/triggers", self._create)
        app.router.add_put("/api/triggers/{id}", self._save)
        app.router.add_patch("/api/triggers/{id}", self._update)
        app.router.add_post("/api/triggers/{id}/run", self._run)
        app.router.add_post("/api/triggers/{id}/webhook", self._renew_token)
        app.router.add_delete("/api/triggers/{id}", self._delete)

    async def _list(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        now = self._clock.now()
        rows = []
        for trigger in sorted(self._triggers.all(), key=lambda s: s.name):
            upcoming = self._timing.next_after(trigger, now) if trigger.enabled else None
            rows.append(
                {
                    **trigger.model_dump(mode="json", exclude={"webhook_token_sha256"}),
                    "webhook": trigger.webhook,
                    "next_run": upcoming.isoformat() if upcoming else None,
                }
            )
        return web.json_response(
            {
                "triggers": rows,
                "users": [{"id": u.id, "name": u.name} for u in self._users.all()],
                "agents": [a.name for a in self._agents.delegates()],
            }
        )

    async def _create(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, TriggerRequest)
        token = WebhookToken.new() if body.webhook else None
        trigger = self._build(
            {
                **self._fields(body, token, None),
                "id": self._ids.new_id(),
                "created_at": self._clock.now(),
            }
        )
        await self._triggers.put(trigger)
        return web.json_response({"id": trigger.id, "token": token}, status=201)

    async def _save(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        current = self._get(request)
        body = await RequestBody.parse(request, TriggerRequest)
        token = WebhookToken.new() if body.webhook and not current.webhook else None
        fields = self._fields(body, token, current.webhook_token_sha256)
        if body.once_at is not None:
            fields["last_fired_at"] = None  # a one-off fires while this is unset
        elif body.cron != current.cron or body.timezone != current.timezone:
            fields["last_fired_at"] = self._clock.now()
        trigger = self._build({**current.model_dump(), **fields})
        await self._triggers.put(trigger)
        return web.json_response({"ok": True, "token": token})

    @staticmethod
    def _fields(body: TriggerRequest, token: str | None, kept: str | None) -> dict[str, object]:
        """The request as `Trigger` fields: the webhook flag becomes the hash of a
        new token, the one kept, or none."""
        fields: dict[str, object] = body.model_dump(exclude={"webhook"})
        if not body.webhook:
            fields["webhook_token_sha256"] = None
        else:
            fields["webhook_token_sha256"] = WebhookToken.hash(token) if token else kept
        return fields

    async def _renew_token(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        trigger = self._get(request)
        token = WebhookToken.new()
        await self._triggers.put(
            trigger.model_copy(update={"webhook_token_sha256": WebhookToken.hash(token)})
        )
        return web.json_response({"token": token})

    def _build(self, data: dict[str, object]) -> Trigger:
        if self._users.get(str(data["user_id"])) is None:
            raise web.HTTPBadRequest(text="no such user")
        if data.get("agent") == AgentCatalog.ORCHESTRATOR:
            data = {**data, "agent": None}
        try:
            self._agents.main(data.get("agent"))  # type: ignore[arg-type]
        except AgentUnavailableError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        try:
            return Trigger.model_validate(data)
        except (ValueError, KeyError, ValidationError) as exc:  # KeyError: unknown zone
            raise web.HTTPBadRequest(text=str(exc)) from exc

    async def _update(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        trigger = self._get(request)
        body = await RequestBody.parse(request, TriggerUpdate)
        await self._triggers.put(trigger.model_copy(update={"enabled": body.enabled}))
        return web.json_response({"ok": True})

    async def _run(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        task = asyncio.create_task(self._runner.run(self._get(request)))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return web.json_response({"ok": True}, status=202)

    async def _delete(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        await self._triggers.delete(self._get(request).id)
        return web.json_response({"ok": True})

    def _get(self, request: web.Request) -> Trigger:
        trigger = self._triggers.get(request.match_info["id"])
        if trigger is None:
            raise web.HTTPNotFound(text="no such trigger")
        return trigger
