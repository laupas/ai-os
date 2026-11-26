import re
from typing import Any

from aios.variables.variable_resolver import REFERENCE

VARIABLES_KEY = "variables"
"""In a code connector's config: the Variable each declared variable is read from,
`{declared: variable}`. Without it, a declared variable is read under its own name."""


class ConnectorVariableNames:
    """Variable names of one connector among several of the same kind, so each can
    have its own key or account: a second GitHub connector reads `GITHUB_WORK_TOKEN`
    where the first reads `GITHUB_TOKEN`."""

    @staticmethod
    def scoped(connector_id: str, name: str) -> str:
        """`name` for the connector `connector_id`: `github-work`, `GITHUB_TOKEN` gives
        `GITHUB_WORK_GITHUB_TOKEN`."""
        prefix = re.sub(r"[^A-Za-z0-9]", "_", connector_id).upper()
        return f"{prefix}_{name}"

    @staticmethod
    def mapping(config: dict[str, Any]) -> dict[str, str]:
        """A code connector's `{declared: variable}`, whatever is malformed left out."""
        given = config.get(VARIABLES_KEY)
        if not isinstance(given, dict):
            return {}
        return {k: v for k, v in given.items() if isinstance(k, str) and isinstance(v, str)}

    @staticmethod
    def renamed(value: Any, names: dict[str, str]) -> Any:
        """`value` with each `${OLD}` and `${file:OLD}` in `names` referring to the new name."""
        if isinstance(value, str):

            def replace(match: re.Match[str]) -> str:
                name = names.get(match.group(2))
                return match.group(0) if name is None else f"${{{match.group(1) or ''}{name}}}"

            return REFERENCE.sub(replace, value)
        if isinstance(value, list):
            return [ConnectorVariableNames.renamed(v, names) for v in value]
        if isinstance(value, dict):
            return {k: ConnectorVariableNames.renamed(v, names) for k, v in value.items()}
        return value
