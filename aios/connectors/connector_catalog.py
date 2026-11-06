import os
from typing import Any, Protocol

from aios.connectors.code_connectors import CodeConnectors
from aios.connectors.connector_tokens import ConnectorTokens
from aios.connectors.oauth_client_config import OAuthClientConfig
from aios.entities.connectors.connector import Connector
from aios.entities.connectors.sign_in_mode import SignInMode
from aios.entities.users.user import User
from aios.storage.collection import Collection


class Expander(Protocol):
    def expand(self, value: Any) -> Any: ...


class ConnectorCatalog:
    """The MCP servers ai-os starts for a turn: the built-in `aios` server, always,
    and every enabled stored connector.

    Read on every turn, so a change in the console applies to the next turn. Which
    account a signed-in connector uses depends on who the turn is for: see
    `ConnectorTokens.for_turn`.
    """

    BUILTIN = "aios"
    OAUTH_KEY = "oauth"
    """ai-os's own key in a connector's config; never passed on to Claude Code."""

    def __init__(
        self,
        connectors: Collection[Connector],
        builtin_tools: list[str],
        tokens: ConnectorTokens | None = None,
        expander: Expander | None = None,
        code: CodeConnectors | None = None,
    ) -> None:
        self._code = code
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

    def enabled_names(self) -> list[str]:
        return [c.id for c in self.all() if c.enabled]

    def servers(self, user: User | None = None) -> dict[str, dict[str, Any]]:
        """The external servers' configs for a turn of `user`, with `${VAR}` filled in
        and the sign-in that turn uses as the `Authorization` header.

        A per-user connector the user has not signed in to is left out: given to the
        CLI without a token, it would try to sign in by itself and fail."""
        missing = set(self.unavailable_for(user))
        configs = {c.id: self._launch(c) for c in self.all() if c.enabled and c.id not in missing}
        return {
            name: self._with_token(self._connectors.get(name), user, self._expand(config))  # type: ignore[arg-type]
            for name, config in configs.items()
            if config is not None
        }

    def unavailable_for(self, user: User | None) -> list[str]:
        """Enabled per-user connectors left out of `user`'s turns until they sign in."""
        if self._tokens is None:
            return []
        return [
            c.id
            for c in self.all()
            if c.enabled
            and c.sign_in is SignInMode.PER_USER
            and "url" in c.config
            and self._tokens.for_turn(c, user) is None
        ]

    def _with_token(
        self, connector: Connector, user: User | None, config: dict[str, Any]
    ) -> dict[str, Any]:
        token = self._tokens.for_turn(connector, user) if self._tokens is not None else None
        if token is None or "url" not in config:
            return config
        headers = {**(config.get("headers") or {}), "Authorization": f"Bearer {token.access_token}"}
        return {**config, "headers": headers}

    def server_config(self, name: str, user: User | None = None) -> dict[str, Any] | None:
        """One connector's config as a turn of `user` would start it, enabled or not."""
        connector = self._connectors.get(name)
        config = self._launch(connector) if connector else None
        if connector is None or config is None:
            return None
        return self._with_token(connector, user, self._expand(config))

    def oauth_of(self, name: str) -> OAuthClientConfig | None:
        """The connector's own OAuth client, with `${VAR}` filled in, if it has one."""
        connector = self._connectors.get(name)
        raw = connector.config.get(self.OAUTH_KEY) if connector else None
        return OAuthClientConfig.model_validate(self._expand(raw)) if raw else None

    def _launch(self, connector: Connector) -> dict[str, Any] | None:
        """What Claude Code is given to start it: a code connector's own launch, or
        the config minus ai-os's keys. None for a code connector that is gone."""
        if self._code is not None and CodeConnectors.is_code(connector):
            return self._code.launch_config(connector)
        return {k: v for k, v in connector.config.items() if k != self.OAUTH_KEY}

    def tool_prefixes(self) -> list[str]:
        return [f"mcp__{name}__" for name in [self.BUILTIN, *self.enabled_names()]]

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
