from datetime import timedelta

from aiohttp import web

from aios.common.clock import Clock
from aios.entities.users.permission import Permission
from aios.logs.log_reader import LEVELS, LogReader
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class LogRoutes(WebRoutes):
    """ai-os's own log, filtered by level and age. Administrators only."""

    def __init__(self, log_reader: LogReader, clock: Clock) -> None:
        self._log_reader = log_reader
        self._clock = clock

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/logs", self._logs)

    async def _logs(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        level = request.query.get("level", "WARNING").upper()
        if level not in LEVELS:
            raise web.HTTPBadRequest(text=f"level must be one of {LEVELS}")
        try:
            hours = max(1, min(int(request.query.get("hours", "24")), 24 * 14))
        except ValueError as exc:
            raise web.HTTPBadRequest(text="hours must be a number") from exc
        since = self._clock.now() - timedelta(hours=hours)
        return web.json_response({"lines": self._log_reader.read(since, level)})
