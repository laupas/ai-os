from typing import Any

from pydantic import BaseModel

from aios.entities.connectors.sign_in_mode import SignInMode


class Connector(BaseModel):
    """An external MCP server agents may be granted. `id` is the server name.

    `config` is Claude Code's `.mcp.json` shape. `${VAR}` in a value is replaced from
    the environment when the server is started, so secrets stay in env vars.
    """

    id: str
    description: str = ""
    config: dict[str, Any]
    enabled: bool = True
    sign_in: SignInMode = SignInMode.SHARED
    """Whose account an OAuth sign-in is; only matters for a server signed in to."""
    shared_fallback: bool = False
    """With `per_user`: whether a user who has not signed in uses the shared account.
    Off by default, so nobody ends up working in somebody else's account."""
