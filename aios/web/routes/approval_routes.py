from aiohttp import web

from aios.approvals.approval_service import ApprovalService
from aios.entities.approvals.approval import Approval
from aios.entities.approvals.approval_status import ApprovalStatus
from aios.entities.users.permission import Permission
from aios.storage.collection import Collection
from aios.web.answer_request import AnswerRequest
from aios.web.request_body import RequestBody
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class ApprovalRoutes(WebRoutes):
    """Pending approvals from every channel, answerable here. Whether the caller may
    answer one is decided by `ApprovalService`, exactly as for a Slack button."""

    def __init__(self, approvals: Collection[Approval], service: ApprovalService) -> None:
        self._approvals = approvals
        self._service = service

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/approvals", self._pending)
        app.router.add_post("/api/approvals/{id}", self._answer)

    async def _pending(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.APPROVE)
        pending = self._approvals.filter(lambda a: a.status is ApprovalStatus.PENDING)
        pending.sort(key=lambda a: a.created_at, reverse=True)
        return web.json_response(
            {
                "approvals": [
                    {
                        "id": a.id,
                        "conversation_id": a.conversation_id,
                        "channel": a.binding.channel,
                        "question": a.question,
                        "options": a.options,
                        "created_at": a.created_at.isoformat(),
                    }
                    for a in pending
                ]
            }
        )

    async def _answer(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        body = await RequestBody.parse(request, AnswerRequest)
        if not await self._service.answer(request.match_info["id"], body.answer, caller.account):
            raise web.HTTPConflict(text="not pending any more, or you may not answer it")
        return web.json_response({"ok": True})
