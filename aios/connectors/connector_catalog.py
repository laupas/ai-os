import os
from typing import Any, Protocol

from aios.connectors.oauth_client_config import OAuthClientConfig
from aios.entities.connectors.connector import Connector
from aios.entities.connectors.connector_token import ConnectorToken
from aios.storage.collection import Collection


class Expander(Protocol):
    def expand(self, value: Any) -> Any: ...


class ConnectorCatalog:
    """The MCP servers ai-os starts for a turn: the built-in `aios` server, always,
    and every enabled stored connector.

    Read on every turn, so a change in the console applies to the next turn.
    """

    BUILTIN = "aios"
    OAUTH_KEY = "oauth"
    """ai-os's own key in a connector's config; never passed on to Claude Code."""

    def __init__(
        self,
        connectors: Collection[Connector],
        builtin_tools: list[str],
        tokens: Collection[ConnectorToken] | None = None,
        expander: Expander | None = None,
    ) -> None:
        self._expander = expander
        self._connectors = connectors
        self._builtin_tools = builtin_tools
        self._tokens = tokens

    def all(self) -> list[Connector]:
        return sorted(self._connectors.all(), key=lambda c: c.id)

    def get(self, name: str) -> Connector | None:
        return self._connectors.get(name)

    def builtin_tools(self) -> list[str]:
        return list(self._builtin_tools)

    def is_enabled(self, name: str) -> bool:
        if name == self.BUILTIN:
            return True
        connector = self._connectors.get(name)
        return connector is not None and connector.enabled

    def servers(self) -> dict[str, dict[str, Any]]:
        """The external servers' configs, with `${VAR}` filled in from the environment
        and a signed-in connector's token as its `Authorization` header."""
        return {
            c.id: self._with_token(c.id, self._expand(self._server_part(c.config)))
            for c in self.all()
            if c.enabled
        }

    def _with_token(self, name: str, config: dict[str, Any]) -> dict[str, Any]:
        token = self._tokens.get(name) if self._tokens is not None else None
        if token is None or "url" not in config:
            return config
        headers = {**(config.get("headers") or {}), "Authorization": f"Bearer {token.access_token}"}
        return {**config, "headers": headers}

    def server_config(self, name: str) -> dict[str, Any] | None:
        """One connector's config as a turn would start it, enabled or not."""
        connector = self._connectors.get(name)
        if connector is None:
            return None
        return self._with_token(name, self._expand(self._server_part(connector.config)))

    def oauth_of(self, name: str) -> OAuthClientConfig | None:
        """The connector's own OAuth client, with `${VAR}` filled in, if it has one."""
        connector = self._connectors.get(name)
        raw = connector.config.get(self.OAUTH_KEY) if connector else None
        return OAuthClientConfig.model_validate(self._expand(raw)) if raw else None

    def _server_part(self, config: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in config.items() if k != self.OAUTH_KEY}

    def tool_prefixes(self) -> list[str]:
        return [f"mcp__{name}__" for name in [self.BUILTIN, *self.servers()]]

    def _expand(self, value: Any) -> Any:
        if self._expander is not None:
            return self._expander.expand(value)
        if isinstance(value, str):
            return os.path.expandvars(value)
        if isinstance(value, list):
            return [self._expand(v) for v in value]
        if isinstance(value, dict):
            return {k: self._expand(v) for k, v in value.items()}
        return value
