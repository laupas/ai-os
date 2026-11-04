from pydantic import BaseModel

from aios.conversations.attachment import Attachment
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.channel_account import ChannelAccount


class InboundMessage(BaseModel):
    """A message a channel received, before anything has been decided about it."""

    binding: ChannelBinding
    sender: ChannelAccount
    text: str
    attachments: list[Attachment] = []
