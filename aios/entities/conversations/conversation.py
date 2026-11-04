from datetime import datetime

from pydantic import BaseModel

from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.conversation_status import ConversationStatus


class Conversation(BaseModel):
    """A conversation, independent of the channel it started on."""

    id: str
    title: str | None = None
    participants: list[str] = []
    bindings: list[ChannelBinding] = []
    agent_session_id: str | None = None
    agent: str | None = None
    """The agent that answers here instead of the orchestrator. Set when the
    conversation starts and kept, since its session belongs to that agent."""
    status: ConversationStatus = ConversationStatus.OPEN
    created_at: datetime
    updated_at: datetime

    def is_bound_to(self, binding: ChannelBinding) -> bool:
        return any(b.same_place(binding) for b in self.bindings)
