from pydantic import BaseModel, Field


class StartConversationRequest(BaseModel):
    """The first message of a web conversation, and who should answer it."""

    text: str = Field(min_length=1)
    agent: str | None = None
    """An agent to talk to directly; None (or the orchestrator) is the usual way."""
