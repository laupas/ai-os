"""Hello world, the example code connector.

ai-os starts it in one of two ways:

- `server.py`: an MCP session over stdio, for a turn;
- `server.py preflight <tool> <arguments>`: before a human is asked to approve a
  call, it prints one JSON line, `{"deny": "why"}` or `{"ask": "question"}`.

What it gets from ai-os, all in the environment:

- AIOS_CONNECTOR_SETTINGS: the settings as JSON (defaults, then the connector's,
  then what aios.yaml fixes);
- AIOS_CONNECTOR_STATE: a folder of its own that outlives restarts;
- AIOS_TIMEZONE: the user's timezone;
- whatever its manifest lists under `env`, here HELLO_TOKEN.

It runs with ai-os's Python, so pydantic, aiohttp and the `mcp` package are there.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer

SETTINGS = {"greeting": "Hello", "max_shout_length": 20} | json.loads(
    os.environ.get("AIOS_CONNECTOR_SETTINGS") or "{}"
)
STATE = Path(os.environ.get("AIOS_CONNECTOR_STATE") or ".")
COUNTER = STATE / "greeted.json"


def _token() -> str | None:
    # A variable that is set nowhere arrives as its own `${NAME}`.
    value = os.environ.get("HELLO_TOKEN", "")
    return None if not value or value.startswith("${") else value


def _greeted() -> int:
    return json.loads(COUNTER.read_text())["count"] if COUNTER.exists() else 0


def preflight(tool: str, arguments: dict) -> dict:
    """Asked before a human is: refuse what would fail anyway, word the rest."""
    text = str(arguments.get("text", ""))
    limit = SETTINGS["max_shout_length"]
    if len(text) > limit:
        return {"deny": f"{len(text)} characters is too long to shout (at most {limit})"}
    return {"ask": f"Shout {text!r}?"}


def server() -> MCPServer:
    mcp = MCPServer("hello-world")

    @mcp.tool()
    def hello(name: str) -> str:
        """Greets someone, and counts the greetings across restarts."""
        count = _greeted() + 1
        STATE.mkdir(parents=True, exist_ok=True)
        COUNTER.write_text(json.dumps({"count": count}))
        now = datetime.now(ZoneInfo(os.environ.get("AIOS_TIMEZONE") or "UTC"))
        return f"{SETTINGS['greeting']}, {name}! (greeting number {count}, {now:%H:%M})"

    @mcp.tool()
    def shout(text: str) -> str:
        """The text in capitals. A human approves every call first."""
        return text.upper()

    @mcp.tool()
    def status() -> str:
        """What this connector was given: its settings, whether the token is set,
        and the names (never the values) of the variables it can see."""
        return json.dumps(
            {
                "settings": SETTINGS,
                "token_set": _token() is not None,
                "greeted": _greeted(),
                "environment": sorted(os.environ),
            }
        )

    return mcp


if __name__ == "__main__":
    if sys.argv[1:2] == ["preflight"]:
        print(json.dumps(preflight(sys.argv[2], json.loads(sys.argv[3]))))
    else:
        server().run()
