from aiohttp import web

from aios.conversations.artifact_store import ArtifactStore
from aios.entities.artifacts.artifact_format import ArtifactFormat
from aios.entities.conversations.conversation import Conversation
from aios.entities.users.permission import Permission
from aios.storage.collection import Collection
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes

# An agent wrote the page, maybe steered by what it read: it runs sandboxed, in an
# origin of its own (no `allow-same-origin`), so it reaches neither the session nor
# the API, and it can load scripts from two CDNs but send nothing anywhere.
HTML_CSP = "; ".join(
    [
        "sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox allow-modals",
        "default-src 'none'",
        "script-src 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
        "style-src 'unsafe-inline'",
        "img-src data: blob:",
        "font-src data:",
        "media-src data: blob:",
        "connect-src 'none'",
        "form-action 'none'",
        "base-uri 'none'",
        "frame-ancestors 'self'",
    ]
)
# Markdown is shown as text: nothing in it runs.
TEXT_CSP = "default-src 'none'; sandbox; frame-ancestors 'self'"


class ArtifactRoutes(WebRoutes):
    """Serves the artifacts agents made in conversations.

    Whoever may read the conversation may open its artifacts (its participants,
    administrators all of them), the same rule as `ConversationRoutes`. A page is
    served with a policy of its own (`HTML_CSP`), never the console's.
    """

    def __init__(self, artifacts: ArtifactStore, conversations: Collection[Conversation]) -> None:
        self._artifacts = artifacts
        self._conversations = conversations

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/artifacts/{id}", self._read)

    async def _read(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        artifact = await self._artifacts.get(request.match_info["id"])
        conversation = (
            self._conversations.get(artifact.conversation_id) if artifact is not None else None
        )
        if artifact is None or conversation is None:
            raise web.HTTPNotFound(text="no such artifact")
        if (
            not caller.can(Permission.ADMINISTER)
            and caller.user.id not in conversation.participants
        ):
            raise web.HTTPNotFound(text="no such artifact")
        html = artifact.format is ArtifactFormat.HTML
        headers = {
            "Content-Security-Policy": HTML_CSP if html else TEXT_CSP,
            "X-Frame-Options": "SAMEORIGIN",
            "Cache-Control": "private, no-store",
        }
        if request.query.get("download"):
            headers["Content-Disposition"] = f'attachment; filename="{artifact.file_name}"'
        return web.Response(
            text=artifact.content,
            content_type=artifact.format.mime_type if html else "text/plain",
            charset="utf-8",
            headers=headers,
        )
