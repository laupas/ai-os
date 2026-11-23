import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from aiohttp import web

from aios.common.clock import Clock
from aios.config.triggers_config import TriggersConfig
from aios.entities.triggers.trigger import Trigger
from aios.storage.collection import Collection
from aios.triggers.trigger_runner import TriggerRunner
from aios.triggers.webhook_token import WebhookToken
from aios.web.web_routes import WebRoutes

log = logging.getLogger(__name__)


class TriggerHookRoutes(WebRoutes):
    """`POST /hooks/triggers/{id}`: starts a run of a trigger that has a webhook.

    The only routes outside the console's sign-in: the caller is a program, and
    `Authorization: Bearer <token>` is its whole proof. An unknown trigger, one
    without a webhook and a wrong token all answer 404, so the answer tells a
    guesser nothing. The body, if any, reaches the run as data below the prompt.

    A trigger starts at most once per `COOLDOWN`, so a sender stuck in a loop
    cannot start agent turns without end. `triggers` switched off in aios.yaml
    stops these runs as it stops the timed ones.
    """

    COOLDOWN = timedelta(seconds=10)

    def __init__(
        self,
        triggers: Collection[Trigger],
        runner: TriggerRunner,
        clock: Clock,
        config: Callable[[], TriggersConfig],
    ) -> None:
        self._triggers = triggers
        self._runner = runner
        self._clock = clock
        self._config = config
        self._last: dict[str, datetime] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    def register(self, app: web.Application) -> None:
        app.router.add_post("/hooks/triggers/{id}", self._trigger)
        # Until 2026-11-23 triggers were schedules: callers set up then keep working.
        app.router.add_post("/hooks/schedules/{id}", self._trigger)

    async def _trigger(self, request: web.Request) -> web.Response:
        trigger = self._triggers.get(request.match_info["id"])
        token = self._token(request)
        if (
            trigger is None
            or token is None
            or not WebhookToken.matches(token, trigger.webhook_token_sha256)
        ):
            raise web.HTTPNotFound(text="no such webhook")
        if not trigger.enabled:
            raise web.HTTPConflict(text="the trigger is switched off")
        if not self._config().enabled:
            raise web.HTTPServiceUnavailable(text="the triggers is switched off")
        now = self._clock.now()
        last = self._last.get(trigger.id)
        if last is not None and now - last < self.COOLDOWN:
            raise web.HTTPTooManyRequests(text="started a moment ago; try again shortly")
        self._last[trigger.id] = now
        payload = await self._payload(request)
        log.info("trigger %s started by its webhook", trigger.name)
        task = asyncio.create_task(self._runner.run(trigger, payload))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return web.json_response({"ok": True}, status=202)

    @staticmethod
    def _token(request: web.Request) -> str | None:
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        return token.strip() or None if scheme.casefold() == "bearer" else None

    @staticmethod
    async def _payload(request: web.Request) -> str | None:
        try:
            text = await request.text()
        except UnicodeDecodeError as exc:
            raise web.HTTPBadRequest(text="the body must be text") from exc
        if not text.strip():
            return None
        if request.content_type == "application/json":
            try:
                return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
            except ValueError:
                pass
        return text
