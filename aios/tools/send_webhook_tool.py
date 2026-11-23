import json
from typing import Any

from aios.conversations.message_recorder import MessageRecorder
from aios.entities.conversations.message_role import MessageRole
from aios.entities.webhooks.webhook_destination import WebhookDestination
from aios.messaging.webhook.webhook_poster import WebhookPoster
from aios.storage.collection import Collection
from aios.tools.aios_tool import AiosTool
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError


class SendWebhookTool(AiosTool):
    """Posts to a webhook destination set up in the console. Whether that needs
    approval is decided by `SendWebhookApprovalRule` before this runs. The
    destinations are read for every turn, so a new one needs no restart."""

    NAME = "send_webhook"

    def __init__(
        self,
        destinations: Collection[WebhookDestination],
        poster: WebhookPoster,
        recorder: MessageRecorder,
    ) -> None:
        self._destinations = destinations
        self._poster = poster
        self._recorder = recorder

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        usable = self._usable()
        if not usable:
            return "Post to a webhook destination. None is set up or the channel is off."
        lines = [
            f"- {d.id}: {d.description or 'no description'} "
            f"Fields: {json.dumps(d.fields.get('properties', {}), ensure_ascii=False)}"
            f"{' Required: ' + ', '.join(d.fields['required']) if d.fields.get('required') else ''}"
            for d in usable
        ]
        return (
            "Post to a webhook destination, giving the fields it declares. Posts may need a "
            "human's approval, which is asked automatically. Destinations:\n" + "\n".join(lines)
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "enum": [d.id for d in self._usable()] or ["none"],
                },
                "fields": {"type": "object", "description": "As the destination declares them"},
            },
            "required": ["destination", "fields"],
        }

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        if not self._poster.enabled:
            raise ToolError("The webhook channel is off.")
        name = str(args["destination"])
        destination = self._destinations.get(name)
        if destination is None or not destination.enabled:
            raise ToolError(f"No webhook destination called {name!r}.")
        fields = args.get("fields") or {}
        if not isinstance(fields, dict):
            raise ToolError("`fields` must be an object.")
        result = await self._poster.post(destination, fields)
        outcome = "sent" if result.ok else f"FAILED ({result.detail})"
        await self._recorder.record(
            context.conversation_id,
            MessageRole.TOOL,
            f"webhook {name} {outcome}:\n{json.dumps(fields, ensure_ascii=False, indent=2)}",
            context.binding.channel,
            context.user.id,
        )
        if not result.ok:
            raise ToolError(f"Posting failed: {result.detail}")
        return f"Posted to {name}: {result.detail}"

    def _usable(self) -> list[WebhookDestination]:
        if not self._poster.enabled:
            return []
        return sorted((d for d in self._destinations.all() if d.enabled), key=lambda d: d.id)
