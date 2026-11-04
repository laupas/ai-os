from claude_agent_sdk import Message
from claude_agent_sdk.types import StreamEvent

from aios.engine.text_delta import TextDelta


class TextStreamMapper:
    """Picks the main agent's text out of the SDK's partial-message stream.
    Subagents' streams (those with a parent tool use) are not the reply."""

    def delta(self, message: Message) -> TextDelta | None:
        if not isinstance(message, StreamEvent) or message.parent_tool_use_id is not None:
            return None
        event = message.event
        if event.get("type") == "message_start":
            return TextDelta(text="", restart=True)
        delta = event.get("delta") or {}
        if event.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
            return TextDelta(text=delta.get("text", ""))
        return None
