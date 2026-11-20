from enum import StrEnum


class ChannelCapability(StrEnum):
    """What a channel can do: be talked with, or send messages on ai-os's behalf."""

    CHAT = "chat"
    """People write to ai-os there and get the reply there (`MessageChannel`)."""
    SEND = "send"
    """Agents can send a message to a user's account there (`MessageSender`)."""
