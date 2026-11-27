from pydantic import BaseModel


class MemorySource(BaseModel):
    """Where a memory was last written: set by ai-os, never by the agent writing it."""

    channel: str
    """The turn's channel (`slack`, `web`, …), or `console` for the memories page."""
    conversation_id: str | None = None
    """The conversation whose turn wrote it; None from the console."""
    user_id: str | None = None
    """Who wrote it: the turn's user, or who saved it in the console."""
