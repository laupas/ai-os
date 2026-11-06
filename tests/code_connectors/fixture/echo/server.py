"""A code connector for the tests: `echo` answers with the greeting, `shout` is
approved first and refused by its preflight when the text is too long."""

import json
import os
import sys

from mcp.server.mcpserver import MCPServer

settings = json.loads(os.environ.get("AIOS_CONNECTOR_SETTINGS") or "{}")


def preflight(tool: str, arguments: dict) -> dict:
    text = str(arguments.get("text", ""))
    if len(text) > settings.get("max_length", 10):
        return {"deny": f"{len(text)} characters is too long to shout"}
    return {"ask": f"Shout {text!r}?"}


if __name__ == "__main__":
    if sys.argv[1:2] == ["preflight"]:
        print(json.dumps(preflight(sys.argv[2], json.loads(sys.argv[3]))))
        sys.exit(0)
    server = MCPServer("echo")

    @server.tool()
    def echo(text: str) -> str:
        """Answers with the greeting and the text, and says which variables it can see."""
        seen = sorted(k for k in os.environ if k.startswith(("AIOS_", "ECHO_", "SLACK_")))
        return json.dumps({"text": f"{settings.get('greeting', 'hello')} {text}", "env": seen})

    @server.tool()
    def shout(text: str) -> str:
        """The text in capitals."""
        return text.upper()

    server.run()
