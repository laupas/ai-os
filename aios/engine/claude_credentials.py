from typing import Literal

from aios.variables.variable_resolver import VariableResolver

VARIABLES = {"subscription": "CLAUDE_CODE_OAUTH_TOKEN", "api_key": "ANTHROPIC_API_KEY"}


class ClaudeCredentials:
    """The environment that signs the Claude CLI in, the way `agent.auth` says.

    The value comes from the variable of that name in the console, else from the
    process environment, and is read for every turn: a new key applies to the next
    one. The other credential is blanked, so a leftover one in the environment can
    never be the one used.
    """

    def __init__(
        self, auth: Literal["subscription", "api_key"], resolver: VariableResolver
    ) -> None:
        self._auth = auth
        self._resolver = resolver

    @property
    def variable(self) -> str:
        return VARIABLES[self._auth]

    @staticmethod
    def variable_for(auth: Literal["subscription", "api_key"]) -> str:
        return VARIABLES[auth]

    def env(self) -> dict[str, str]:
        return self.env_for(self._auth)

    def env_for(
        self, auth: Literal["subscription", "api_key"], value: str | None = None
    ) -> dict[str, str]:
        """The environment for `auth` rather than the configured one, with `value`
        in place of the stored credential when given: to try one before using it."""
        env = {name: "" for name in VARIABLES.values()}
        value = value or self._resolver.value_of(VARIABLES[auth])
        if value:
            env[VARIABLES[auth]] = value
        return env

    def status(self) -> dict[str, str | None]:
        """For the console: which credential, and where it comes from. Never the value."""
        return {
            "auth": self._auth,
            "variable": self.variable,
            "source": self._resolver.source_of(self.variable),
        }
