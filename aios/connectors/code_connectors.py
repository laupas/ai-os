import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from aios.agents.repo_agent_reader import RepoAgentReader
from aios.config.connector_override import ConnectorOverride
from aios.connectors.code_connector_launcher import BASE
from aios.connectors.code_connector_library import CodeConnectorLibrary
from aios.connectors.code_connector_manifest import CodeConnectorManifest
from aios.entities.agents.agent import Agent
from aios.entities.connectors.connector import Connector
from aios.storage.storage_name import StorageName

CODE_KEY = "code"
"""In a connector's config: the name of the code connector it runs."""
SETTINGS_KEY = "settings"
"""In a connector's config: its settings, under what aios.yaml fixes."""
LAUNCHER = "aios.connectors.code_connector_launcher"
PREFLIGHT_TIMEOUT_SECONDS = 20


class CodeConnectors:
    """Runs connectors written as code: a Python MCP server in its own process,
    started with only the environment its manifest declares.

    Settings are the manifest's defaults, then what is set on the connector, then
    what aios.yaml fixes under `connectors.<name>.settings`.
    """

    def __init__(
        self,
        library: CodeConnectorLibrary,
        overrides: dict[str, ConnectorOverride],
        state_root: Path,
        timezone: str,
    ) -> None:
        self._library = library
        self._overrides = overrides
        self._state_root = Path(state_root)
        self._timezone = timezone

    @property
    def library(self) -> CodeConnectorLibrary:
        return self._library

    @staticmethod
    def agents_of(manifest: CodeConnectorManifest) -> list[Agent]:
        """The agents that ship with a code connector, in its `agents/` folder, in
        the same form as ai-os's own seeds. Offered when the connector is added."""
        return RepoAgentReader(manifest.server_path.parent / "agents").read()

    @staticmethod
    def is_code(connector: Connector) -> bool:
        return CODE_KEY in connector.config

    def manifest_of(self, connector: Connector) -> CodeConnectorManifest | None:
        name = connector.config.get(CODE_KEY)
        return self._library.get(name) if isinstance(name, str) else None

    def fixed(self, connector: Connector) -> dict[str, Any]:
        """The settings aios.yaml fixes for this connector."""
        override = self._overrides.get(connector.id)
        return dict(override.settings) if override else {}

    def settings(self, connector: Connector) -> dict[str, Any]:
        manifest = self.manifest_of(connector)
        stored = connector.config.get(SETTINGS_KEY) or {}
        defaults = manifest.defaults() if manifest else {}
        return {**defaults, **stored, **self.fixed(connector)}

    def launch_config(self, connector: Connector) -> dict[str, Any] | None:
        """The stdio server config for Claude Code, `${VAR}` still to be filled in;
        None when the code connector it names does not exist."""
        manifest = self.manifest_of(connector)
        if manifest is None:
            return None
        state = self._state_root / StorageName.check(connector.id)
        state.mkdir(parents=True, exist_ok=True)
        env = {
            **manifest.env,
            "AIOS_CONNECTOR_SETTINGS": json.dumps(self.settings(connector)),
            "AIOS_CONNECTOR_STATE": str(state),
            "AIOS_TIMEZONE": self._timezone,
        }
        return {
            "command": sys.executable,
            "args": ["-m", LAUNCHER, str(manifest.server_path)],
            "env": {**env, "AIOS_CONNECTOR_KEEP": ",".join(env)},
        }

    def preflight(self, config: dict[str, Any], tool: str, arguments: dict[str, Any]) -> dict:
        """Asks the server about a call before a human is: `{"deny": reason}` or
        `{"ask": question}`. `config` is the launch config with variables filled in."""
        result = subprocess.run(
            [config["command"], *config["args"], "preflight", tool, json.dumps(arguments)],
            capture_output=True,
            text=True,
            timeout=PREFLIGHT_TIMEOUT_SECONDS,
            env={**{k: v for k, v in os.environ.items() if k in BASE}, **config["env"]},
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip()[-500:] or f"exit {result.returncode}")
        answer = json.loads(result.stdout.strip().splitlines()[-1])
        if not isinstance(answer, dict) or not ({"ask", "deny"} & answer.keys()):
            raise RuntimeError("preflight answered neither ask nor deny")
        return answer
