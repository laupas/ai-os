from typing import Any
from urllib.parse import urlparse

_AIOS_PREFIX = "mcp__aios__"


class ProgressLabeler:
    """Turns a tool call into a short line a human can follow."""

    def label(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        if tool_name in ("Task", "Agent"):
            agent = tool_input.get("subagent_type") or "an"
            return f"Asking the {agent} agent"
        if tool_name == "WebSearch":
            return f"Searching the web: {tool_input.get('query', '')}".strip()
        if tool_name == "WebFetch":
            host = urlparse(str(tool_input.get("url", ""))).netloc
            return f"Reading {host or 'a web page'}"
        if tool_name == "Skill":
            return f"Using the {tool_input.get('skill', '')} skill".replace("  ", " ")
        if tool_name.startswith(_AIOS_PREFIX):
            return self._aios_label(tool_name.removeprefix(_AIOS_PREFIX), tool_input)
        if tool_name.startswith("mcp__"):
            server, _, action = tool_name.removeprefix("mcp__").partition("__")
            return f"{server}: {action.replace('_', ' ').replace('-', ' ')}"
        if tool_name in ("Read", "Grep", "Glob"):
            return "Looking through notes"
        if tool_name in ("Edit", "Write"):
            return "Writing a note"
        return tool_name

    @staticmethod
    def _aios_label(name: str, tool_input: dict[str, Any]) -> str:
        if name == "send_message":
            via, recipient = tool_input.get("via", ""), tool_input.get("recipient", "")
            return f"Sending a {via} message to {recipient}"
        if name == "ask_human":
            return "Waiting for your answer"
        if name in ("data_put", "data_delete"):
            return f"Changing {tool_input.get('collection', 'data')}"
        if name == "crypto_signal":
            return "Checking the crypto market"
        if name in ("crypto_quote", "crypto_balance"):
            return "Asking Kraken"
        if name == "crypto_trade":
            return "Placing an order on Kraken"
        if name == "read_logs":
            return "Reading the logs"
        if name.startswith("data_"):
            return f"Looking at {tool_input.get('collection', 'data')}"
        return name
