from datetime import datetime

from pydantic import BaseModel

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
