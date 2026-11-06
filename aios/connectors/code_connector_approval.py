from pydantic import BaseModel


class CodeConnectorApproval(BaseModel):
    """Which of a code connector's tools a human approves first."""

    always: list[str] = []
    """Tool names (without the `mcp__<connector>__` prefix) asked every time."""
    preflight: list[str] = []
    """Of those, the ones the connector itself is asked about first, with
    `server.py preflight <tool> <arguments>`: it may refuse the call outright, or
    word the question. A call it refuses is never put to a human."""
