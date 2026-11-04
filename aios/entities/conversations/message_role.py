from enum import StrEnum


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    """Something ai-os did on the user's behalf, e.g. a sent Signal message."""

    ACTIVITY = "activity"
    """The steps of one turn (tools used, agents asked), one per line. Recorded when
    the turn ends, so a client can show them after the fact, as Slack's status
    message does."""
