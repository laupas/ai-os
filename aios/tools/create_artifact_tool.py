from typing import Any

from aios.conversations.artifact_publisher import ArtifactPublisher
from aios.entities.artifacts.artifact_format import ArtifactFormat
from aios.tools.aios_tool import AiosTool
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError

MAX_TITLE = 200
MAX_CONTENT = 2_000_000


class CreateArtifactTool(AiosTool):
    """Makes a document in the turn's conversation, such as the report of a run,
    and shows it wherever the conversation lives (`ArtifactPublisher`)."""

    NAME = "create_artifact"

    def __init__(self, publisher: ArtifactPublisher) -> None:
        self._publisher = publisher

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return (
            "Create a document in this conversation that the user can open and keep, "
            "such as a report of what you did or found. Use it for content longer than "
            "a chat message or meant to be kept; reply with a short summary only, never "
            "the document again. It shows as a card in the web console, as a file on "
            "Slack, and as a link elsewhere. "
            "`html` is one complete, self-contained page: CSS and JavaScript inline; "
            "scripts may also be loaded from https://cdn.jsdelivr.net or "
            "https://cdnjs.cloudflare.com, nothing else is reachable (no fetch, no "
            "external images or fonts: embed data, images as data: URLs). "
            "`markdown` is shown as formatted text."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title, also the file name"},
                "format": {"type": "string", "enum": [f.value for f in ArtifactFormat]},
                "content": {"type": "string"},
            },
            "required": ["title", "format", "content"],
        }

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        title = str(args.get("title") or "").strip()
        content = str(args.get("content") or "")
        if not title or len(title) > MAX_TITLE:
            raise ToolError(f"The title must have 1 to {MAX_TITLE} characters.")
        if not content.strip():
            raise ToolError("The content is empty.")
        if len(content) > MAX_CONTENT:
            raise ToolError(f"The content is longer than {MAX_CONTENT} characters.")
        try:
            format = ArtifactFormat(str(args.get("format")))
        except ValueError as exc:
            raise ToolError("format must be html or markdown.") from exc
        await self._publisher.publish(
            context.conversation_id, context.user, context.binding, title, format, content
        )
        return f"Created the artifact {title!r}; the user sees it in the conversation."
