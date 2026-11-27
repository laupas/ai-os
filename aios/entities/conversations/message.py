from datetime import datetime

from pydantic import BaseModel

from aios.entities.artifacts.artifact_ref import ArtifactRef
from aios.entities.conversations.message_role import MessageRole


class Message(BaseModel):
    """One entry of a conversation's history, kept for UIs on other devices."""

    id: str
    conversation_id: str
    role: MessageRole
    author_user_id: str | None = None
    channel: str
    text: str
    created_at: datetime
    artifact: ArtifactRef | None = None
    """The artifact an `artifact` message presents; its `text` is the title."""
