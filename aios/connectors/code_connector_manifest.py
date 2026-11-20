from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from aios.connectors.code_connector_approval import CodeConnectorApproval
from aios.variables.variable_field import VariableField


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
    values as JSON from `AIOS_CONNECTOR_SETTINGS`."""
    approval: CodeConnectorApproval = CodeConnectorApproval()
    folder: Path | None = None
    """Where it was found; set when it is loaded, never written in the file."""

    @property
    def server_path(self) -> Path:
        assert self.folder is not None
        return self.folder / self.server

    def defaults(self) -> dict[str, Any]:
        return {k: p["default"] for k, p in self._properties().items() if "default" in p}

    def launch_env(self) -> dict[str, str]:
        """`env`, and each declared variable under its own name unless `env` names
        it already."""
        declared = {f.variable: f"${{{f.variable}}}" for f in self.variables}
        return {**declared, **self.env}

    def _properties(self) -> dict[str, dict[str, Any]]:
        return self.settings.get("properties") or {}
