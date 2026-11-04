from pydantic import BaseModel


class ProbeResult(BaseModel):
    """What starting one connector on its own showed."""

    status: str
    """connected, failed, needs-auth, … as Claude Code reports it."""
    error: str | None = None
    server: str | None = None
    """The server's own name and version, from the MCP handshake."""
    tools: list[str] = []
    seconds: float = 0
