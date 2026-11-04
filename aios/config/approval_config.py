from pydantic import BaseModel


class ApprovalConfig(BaseModel):
    always: list[str] = []
    """Tool names that always need a human's approval."""

    deny: list[str] = []
    """Tool names that are never allowed, e.g. write tools of an MCP server."""

    timeout_seconds: int = 1800
    """An unanswered approval is treated as No after this long."""
