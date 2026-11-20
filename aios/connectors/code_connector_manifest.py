from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from aios.connectors.code_connector_approval import CodeConnectorApproval
from aios.variables.variable_field import VariableField

LOCKED = "x-locked"
"""On a setting in the schema: agents cannot change it, only the console can."""
OPTIONS = "x-options"
"""On a value in the schema: the name of a list of choices the server offers for
it, asked with `server.py options <name>`."""


class CodeConnectorManifest(BaseModel):
    """`connector.yaml` beside a code connector's `server.py`: what it is, what it
    needs and what may be configured. `name` is its folder's name."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    server: str = "server.py"
    variables: list[VariableField] = []
    """The values it needs, asked for on its connector in the console and stored as
    Variables (a secret one encrypted), the environment as fallback. Each reaches
    the server under its own name."""
    env: dict[str, str] = {}
    """Passed to the server, `${VAR}` filled in from the variables. Nothing else
    from ai-os's environment reaches it."""
    settings: dict[str, Any] = {"type": "object", "properties": {}}
    """A JSON schema of the settings, with their defaults. The server reads the
    values as JSON from `AIOS_CONNECTOR_SETTINGS`. A setting with `x-locked: true`
    is changed only in the console, never by an agent."""
    approval: CodeConnectorApproval = CodeConnectorApproval()
    check: bool = False
    """The server answers `server.py check` with one JSON line, `{"ok": true|false,
    "detail": "..."}`: whether it works with its settings and variables, e.g. that
    a key is accepted. The console offers it as a Test button."""
    folder: Path | None = None
    """Where it was found; set when it is loaded, never written in the file."""

    @property
    def server_path(self) -> Path:
        assert self.folder is not None
        return self.folder / self.server

    def defaults(self) -> dict[str, Any]:
        return {k: p["default"] for k, p in self._properties().items() if "default" in p}

    def locked(self) -> set[str]:
        return {k for k, p in self._properties().items() if p.get(LOCKED) is True}

    def option_lists(self) -> set[str]:
        """The names given under `x-options` anywhere in the settings' schema."""
        found: set[str] = set()

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                if isinstance(node.get(OPTIONS), str):
                    found.add(node[OPTIONS])
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(self.settings)
        return found

    def launch_env(self) -> dict[str, str]:
        """`env`, and each declared variable under its own name unless `env` names
        it already."""
        declared = {f.variable: f"${{{f.variable}}}" for f in self.variables}
        return {**declared, **self.env}

    def _properties(self) -> dict[str, dict[str, Any]]:
        return self.settings.get("properties") or {}
