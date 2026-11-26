import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aios.agents.repo_agent_reader import RepoAgentReader
from aios.connectors.code_connector_check import CodeConnectorCheck
from aios.connectors.code_connector_launcher import BASE
from aios.connectors.code_connector_library import CodeConnectorLibrary
from aios.connectors.code_connector_manifest import CodeConnectorManifest
from aios.connectors.code_connector_options import CodeConnectorOptions
from aios.connectors.connector_variable_names import ConnectorVariableNames
from aios.entities.agents.agent import Agent
from aios.entities.connectors.connector import Connector
from aios.storage.storage_name import StorageName
from aios.variables.variable_field import VariableField
from aios.variables.variable_resolver import VariableResolver

CODE_KEY = "code"
"""In a connector's config: the name of the code connector it runs."""
SETTINGS_KEY = "settings"
"""In a connector's config: its settings, over the manifest's defaults."""
TOKEN_ENV = "AIOS_ACCESS_TOKEN"
"""A code connector with an `oauth:` client: the access token of the turn's sign-in."""
LAUNCHER = "aios.connectors.code_connector_launcher"
PREFLIGHT_TIMEOUT_SECONDS = 20
CHECK_TIMEOUT_SECONDS = 30
OPTIONS_TIMEOUT_SECONDS = 30


class CodeConnectors:
    """Runs connectors written as code: a Python MCP server in its own process,
    started with only the environment its manifest declares.

    Settings are the manifest's defaults, then what is set on the connector. Those
    the manifest locks are changed only in the console (`ConfigEditor` refuses an
    agent's change). Declared variables reach the server under their own names, a
    field's default standing in for one that is set nowhere. Where they are read
    from is the connector's `variables` map, so two connectors running the same
    code can have their own keys; without one, from the Variable of that name.
    """

    def __init__(
        self,
        library: CodeConnectorLibrary,
        state_root: Path,
        timezone: Callable[[], str],
        resolver: VariableResolver | None = None,
    ) -> None:
        self._library = library
        self._resolver = resolver
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

    def locked(self, connector: Connector) -> set[str]:
        manifest = self.manifest_of(connector)
        return manifest.locked() if manifest else set()

    @staticmethod
    def stored(connector: Connector) -> dict[str, Any]:
        return dict(connector.config.get(SETTINGS_KEY) or {})

    def settings(self, connector: Connector) -> dict[str, Any]:
        manifest = self.manifest_of(connector)
        defaults = manifest.defaults() if manifest else {}
        return {**defaults, **self.stored(connector)}

    @staticmethod
    def fields(connector: Connector, manifest: CodeConnectorManifest) -> list[VariableField]:
        """The manifest's variables as this connector reads them: under its own names."""
        names = ConnectorVariableNames.mapping(connector.config)
        return [
            f.model_copy(update={"variable": names.get(f.variable, f.variable)})
            for f in manifest.variables
        ]

    def launch_config(self, connector: Connector) -> dict[str, Any] | None:
        """The stdio server config for Claude Code, `${VAR}` still to be filled in;
        None when the code connector it names does not exist."""
        manifest = self.manifest_of(connector)
        if manifest is None:
            return None
        state = self._state_root / StorageName.check(connector.id)
        state.mkdir(parents=True, exist_ok=True)
        env = {
            **self._with_defaults(connector, manifest),
            "AIOS_CONNECTOR_SETTINGS": json.dumps(self.settings(connector)),
            "AIOS_CONNECTOR_STATE": str(state),
            "AIOS_TIMEZONE": self._timezone(),
        }
        return {
            "command": sys.executable,
            "args": ["-m", LAUNCHER, str(manifest.server_path)],
            "env": {**env, "AIOS_CONNECTOR_KEEP": ",".join(env)},
        }

    @staticmethod
    def with_token(config: dict[str, Any], access_token: str) -> dict[str, Any]:
        """The launch config with a turn's sign-in, passed like a declared variable.
        Added after `${VAR}` is filled in, so the token is never read as one."""
        env = dict(config["env"])
        env[TOKEN_ENV] = access_token
        env["AIOS_CONNECTOR_KEEP"] = ",".join([*env["AIOS_CONNECTOR_KEEP"].split(","), TOKEN_ENV])
        return {**config, "env": env}

    def _with_defaults(
        self, connector: Connector, manifest: CodeConnectorManifest
    ) -> dict[str, str]:
        names = ConnectorVariableNames.mapping(connector.config)
        env = ConnectorVariableNames.renamed(manifest.launch_env(), names)
        if self._resolver is None:
            return env
        for field in manifest.variables:
            name = names.get(field.variable, field.variable)
            unset = self._resolver.value_of(name) is None
            if field.default is not None and unset and env.get(field.variable) == f"${{{name}}}":
                env[field.variable] = field.default
        return env

    def preflight(self, config: dict[str, Any], tool: str, arguments: dict[str, Any]) -> dict:
        """Asks the server about a call before a human is: `{"deny": reason}` or
        `{"ask": question}`. `config` is the launch config with variables filled in."""
        answer = self._ask(
            config, ["preflight", tool, json.dumps(arguments)], PREFLIGHT_TIMEOUT_SECONDS
        )
        if not ({"ask", "deny"} & answer.keys()):
            raise RuntimeError("preflight answered neither ask nor deny")
        return answer

    def check(self, config: dict[str, Any]) -> CodeConnectorCheck:
        """Asks the server whether it works as configured (`server.py check`). A
        server that fails, or answers something else, did not pass."""
        try:
            answer = self._ask(config, ["check"], CHECK_TIMEOUT_SECONDS)
            return CodeConnectorCheck.model_validate(answer)
        except subprocess.TimeoutExpired:
            return CodeConnectorCheck(ok=False, detail=f"no answer in {CHECK_TIMEOUT_SECONDS} s")
        except (RuntimeError, ValueError) as exc:
            return CodeConnectorCheck(ok=False, detail=str(exc))

    def options(self, config: dict[str, Any], name: str) -> CodeConnectorOptions:
        """The choices the server offers for the list `name` (`server.py options
        <name>`): `{"options": [...]}`, each a value or `{"value", "label"}`."""
        try:
            answer = self._ask(config, ["options", name], OPTIONS_TIMEOUT_SECONDS)
            raw = answer.get("options")
            if not isinstance(raw, list):
                raise ValueError("the server answered no options")
            return CodeConnectorOptions.model_validate(
                {"options": [o if isinstance(o, dict) else {"value": str(o)} for o in raw]}
            )
        except subprocess.TimeoutExpired:
            return CodeConnectorOptions(error=f"no answer in {OPTIONS_TIMEOUT_SECONDS} s")
        except (RuntimeError, ValueError) as exc:
            return CodeConnectorOptions(error=str(exc))

    @staticmethod
    def _ask(config: dict[str, Any], args: list[str], timeout: int) -> dict:
        """Runs the server once with `args`, as a turn would start it, and reads the
        JSON object on the last line it prints."""
        result = subprocess.run(
            [config["command"], *config["args"], *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**{k: v for k, v in os.environ.items() if k in BASE}, **config["env"]},
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip()[-500:] or f"exit {result.returncode}")
        lines = result.stdout.strip().splitlines()
        answer = json.loads(lines[-1]) if lines else None
        if not isinstance(answer, dict):
            raise RuntimeError("the server printed no JSON object")
        return answer
