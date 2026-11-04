from typing import Any

from pydantic import BaseModel


class Connector(BaseModel):
    """An external MCP server agents may be granted. `id` is the server name.

    `config` is Claude Code's `.mcp.json` shape. `${VAR}` in a value is replaced from
    the environment when the server is started, so secrets stay in env vars.
    """

    id: str
    description: str = ""
    config: dict[str, Any]
    enabled: bool = True
