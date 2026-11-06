import re

from aiohttp import web

from aios.audit.audit_feed import AuditFeed
from aios.entities.users.permission import Permission
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes

DEFAULT_LIMIT = 500
MAX_LIMIT = 5000
COMMIT = re.compile(r"^[0-9a-f]{7,40}$")


class AuditRoutes(WebRoutes):
    """Who changed which setting when, from the audit trail and the configuration
    history together. Administrators only."""

    def __init__(self, feed: AuditFeed) -> None:
        self._feed = feed

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/audit", self._list)
        app.router.add_get("/api/audit/commits/{commit}", self._diff)

    async def _list(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        try:
            limit = max(1, min(int(request.query.get("limit", DEFAULT_LIMIT)), MAX_LIMIT))
        except ValueError as exc:
            raise web.HTTPBadRequest(text="limit must be a number") from exc
        entries = await self._feed.entries(limit, request.query.get("area") or None)
        return web.json_response({"entries": [e.model_dump(mode="json") for e in entries]})

    async def _diff(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        commit = request.match_info["commit"]
        if not COMMIT.match(commit):
            raise web.HTTPBadRequest(text="not a commit id")
        diff = await self._feed.diff(commit)
        if diff is None:
            raise web.HTTPNotFound(text="there is no configuration repository")
        return web.json_response({"diff": diff})
