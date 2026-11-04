from typing import Any

from pydantic import BaseModel

from aios.entities.users.user import User


class ToolCall(BaseModel):
    """A tool the agent wants to run, as the approval policy sees it."""

    tool_name: str
    tool_input: dict[str, Any]
    user: User
    conversation_id: str
    agent: str | None = "orchestrator"
    """The agent making the call; None for a subagent ai-os cannot name."""
