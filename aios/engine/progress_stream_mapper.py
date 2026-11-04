from claude_agent_sdk import AssistantMessage, Message, ToolUseBlock

from aios.progress.progress_event import ProgressEvent
from aios.progress.progress_labeler import ProgressLabeler


class ProgressStreamMapper:
    """Picks the tool calls out of the SDK's message stream."""

    def __init__(self, labeler: ProgressLabeler) -> None:
        self._labeler = labeler

    def events(self, message: Message) -> list[ProgressEvent]:
        if not isinstance(message, AssistantMessage):
            return []
        return [
            ProgressEvent(label=self._labeler.label(block.name, block.input), tool_name=block.name)
            for block in message.content
            if isinstance(block, ToolUseBlock)
        ]
