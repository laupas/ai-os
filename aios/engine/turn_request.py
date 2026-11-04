from pydantic import BaseModel

from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.conversation import Conversation
from aios.entities.users.user import User


class TurnRequest(BaseModel):
    """One user message to answer, with who sent it and where."""

    conversation: Conversation
    user: User
    binding: ChannelBinding
    text: str
