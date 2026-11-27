from pydantic import BaseModel

from aios.common.clock import Clock
from aios.entities.memories.memory import Memory
from aios.entities.memories.memory_source import MemorySource
from aios.tools.document_stamp import DocumentStamp
from aios.tools.tool_context import ToolContext


class MemoryStamp(DocumentStamp):
    """A memory keeps the date it was made, and records when and from which turn it
    last changed, so an agent need not (and cannot) write either."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    @property
    def collection(self) -> str:
        return "memories"

    def stamp(self, item: BaseModel, existing: BaseModel | None, context: ToolContext) -> BaseModel:
        assert isinstance(item, Memory)
        now = self._clock.now()
        return item.model_copy(
            update={
                "created_at": existing.created_at if isinstance(existing, Memory) else now,
                "updated_at": now if existing is not None else None,
                "source": MemorySource(
                    channel=context.binding.channel,
                    conversation_id=context.conversation_id,
                    user_id=context.user.id,
                ),
            }
        )
