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
from aios.users.audience import Audience
from aios.web.request_body import RequestBody
from aios.web.trigger_request import TriggerRequest
from aios.web.trigger_update import TriggerUpdate
from aios.web.web_auth import WebAuth
from aios.web.web_caller import WebCaller
from aios.web.web_routes import WebRoutes


class TriggerRoutes(WebRoutes):
    """Lists, creates, edits, switches, runs and deletes triggers. For
    `manage_triggers`: a run acts with its user's rights, so only administrators see
    and write triggers that run for someone else. Every save goes through the
    `Trigger` model, so a bad cron expression, time zone or user is refused here
    rather than at the next tick.

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
        audience: Audience,
    ) -> None:
        self._triggers = triggers
        self._timing = timing
        self._runner = runner
        self._clock = clock
        self._ids = ids
        self._users = users
        self._agents = agents
        self._audience = audience
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
        caller = WebAuth.caller(request, Permission.MANAGE_TRIGGERS)
        admin = caller.can(Permission.ADMINISTER)
        now = self._clock.now()
        rows = []
        mine = [t for t in self._triggers.all() if self._may_touch(caller, t.user_id)]
        for trigger in sorted(mine, key=lambda s: s.name):
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
                "users": [
                    {"id": u.id, "name": u.name}
                    for u in (self._users.all() if admin else [caller.user])
                ],
                "agents": [
                    a.name
                    for a in self._agents.delegates()
                    if admin or self._audience.includes(caller.user, a.available_to)
                ],
            }
        )

    async def _create(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.MANAGE_TRIGGERS)
        body = await RequestBody.parse(request, TriggerRequest)
        self._check_user(caller, body.user_id)
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
        caller = WebAuth.caller(request, Permission.MANAGE_TRIGGERS)
        current = self._get(request, caller)
        body = await RequestBody.parse(request, TriggerRequest)
        self._check_user(caller, body.user_id)
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
        caller = WebAuth.caller(request, Permission.MANAGE_TRIGGERS)
        trigger = self._get(request, caller)
        token = WebhookToken.new()
        await self._triggers.put(
            trigger.model_copy(update={"webhook_token_sha256": WebhookToken.hash(token)})
        )
        return web.json_response({"token": token})

    def _build(self, data: dict[str, object]) -> Trigger:
        user = self._users.get(str(data["user_id"]))
        if user is None:
            raise web.HTTPBadRequest(text="no such user")
        if data.get("agent") == AgentCatalog.ORCHESTRATOR:
            data = {**data, "agent": None}
        try:
            main = self._agents.main(data.get("agent"))  # type: ignore[arg-type]
        except AgentUnavailableError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        if data.get("agent") is not None and not self._audience.includes(user, main.available_to):
            raise web.HTTPBadRequest(
                text=f"the agent {main.id} is not available to {user.name}, "
                "who the trigger runs for"
            )
        try:
            return Trigger.model_validate(data)
        except (ValueError, KeyError, ValidationError) as exc:  # KeyError: unknown zone
            raise web.HTTPBadRequest(text=str(exc)) from exc

    async def _update(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.MANAGE_TRIGGERS)
        trigger = self._get(request, caller)
        body = await RequestBody.parse(request, TriggerUpdate)
        await self._triggers.put(trigger.model_copy(update={"enabled": body.enabled}))
        return web.json_response({"ok": True})

    async def _run(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.MANAGE_TRIGGERS)
        task = asyncio.create_task(self._runner.run(self._get(request, caller)))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return web.json_response({"ok": True}, status=202)

    async def _delete(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.MANAGE_TRIGGERS)
        await self._triggers.delete(self._get(request, caller).id)
        return web.json_response({"ok": True})

    def _get(self, request: web.Request, caller: WebCaller) -> Trigger:
        trigger = self._triggers.get(request.match_info["id"])
        if trigger is None or not self._may_touch(caller, trigger.user_id):
            raise web.HTTPNotFound(text="no such trigger")
        return trigger

    @staticmethod
    def _may_touch(caller: WebCaller, user_id: str) -> bool:
        """A run acts with its user's rights: only administrators write anyone else's."""
        return user_id == caller.user.id or caller.can(Permission.ADMINISTER)

    def _check_user(self, caller: WebCaller, user_id: str) -> None:
        if not self._may_touch(caller, user_id):
            raise web.HTTPForbidden(
                text="only an administrator makes a trigger run for someone else"
            )
