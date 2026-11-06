from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from aios.connectors.code_connector_approval import CodeConnectorApproval


class CodeConnectorManifest(BaseModel):
    """`connector.yaml` beside a code connector's `server.py`: what it is, what it
    needs and what may be configured. `name` is its folder's name."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    server: str = "server.py"
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
        return {
            k: p["default"]
            for k, p in (self.settings.get("properties") or {}).items()
            if "default" in p
        }
