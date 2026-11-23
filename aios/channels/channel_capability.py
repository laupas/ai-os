from enum import StrEnum


class ChannelCapability(StrEnum):
    """What a channel can do: be talked with, send messages to people on ai-os's
    behalf, or post to configured destinations."""

    CHAT = "chat"
    """People write to ai-os there and get the reply there (`MessageChannel`)."""
    SEND = "send"
    """Agents can send a message to a user's account there (`MessageSender`)."""
    WEBHOOK = "webhook"
    """Agents can post to the webhook destinations set up in the console (`send_webhook`)."""
