import json
import logging

from aiohttp import web

from aios.audit.audit_trail import AuditTrail
from aios.entities.audit.audit_action import AuditAction

log = logging.getLogger(__name__)

# Console actions that change settings without storing a document: neither
# `AuditedDocumentStore` nor the configuration history would see them.
# (method, path) -> (area, item, action).
ACTIONS: dict[tuple[str, str], tuple[str, str, AuditAction]] = {
    ("POST", "/api/restart"): ("ai-os", "restart", AuditAction.PERFORMED),
    ("POST", "/api/git/branches"): ("git", "create branch", AuditAction.PERFORMED),
    ("POST", "/api/git/switch"): ("git", "switch branch", AuditAction.PERFORMED),
    ("POST", "/api/git/merge"): ("git", "merge", AuditAction.PERFORMED),
    ("POST", "/api/git/delete"): ("git", "delete branch", AuditAction.PERFORMED),
    ("POST", "/api/git/push"): ("git", "push", AuditAction.PERFORMED),
    ("POST", "/api/git/pull"): ("git", "pull", AuditAction.PERFORMED),
}
# Body fields worth keeping: branch names. Never the body as a whole.
DETAIL_FIELDS = ("name", "start", "branch", "source", "into")


class AuditMiddleware:
    """Records the console actions in `ACTIONS` once they have succeeded. Runs
    inside `WebAuth.middleware`, so the actor is already known."""

    def __init__(self, trail: AuditTrail) -> None:
        self._trail = trail

    @web.middleware
    async def middleware(self, request: web.Request, handler):  # type: ignore[no-untyped-def]
        response = await handler(request)
        action = ACTIONS.get((request.method, request.path))
        if action is not None and response.status < 300:
            area, item, verb = action
            await self._trail.record(area, item, verb, detail=await self._detail(request))
        return response

    @staticmethod
    async def _detail(request: web.Request) -> str | None:
        try:
            body = json.loads(await request.text() or "{}")
        except (ValueError, UnicodeDecodeError):
            return None
        if not isinstance(body, dict):
            return None
        parts = [f"{k}: {body[k]}" for k in DETAIL_FIELDS if isinstance(body.get(k), str)]
        return "; ".join(parts) or None
