from pydantic import BaseModel

from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.user import User


class ToolContext(BaseModel):
    """The turn a tool call belongs to."""

    conversation_id: str
    user: User
    binding: ChannelBinding
