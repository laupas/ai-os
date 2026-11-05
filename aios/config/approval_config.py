from pydantic import BaseModel


class ApprovalConfig(BaseModel):
    always: list[str] = []
    """Tool names that always need a human's approval."""

    deny: list[str] = []
    """Tool names that are never allowed, e.g. write tools of an MCP server."""

    timeout_seconds: int = 86400
    """An unanswered approval is treated as No after this long. The turn waits for it:
    time spent waiting does not count against `agent.turn_timeout_seconds`."""
