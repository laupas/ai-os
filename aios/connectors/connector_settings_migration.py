import logging

import yaml

from aios.bootstrap.startup_step import StartupStep
from aios.config.config_yaml_editor import ConfigYamlEditor
from aios.connectors.code_connectors import SETTINGS_KEY, CodeConnectors
from aios.entities.connectors.connector import Connector
from aios.storage.collection import Collection
from aios.web.aios_yaml_file import AiosYamlFile

log = logging.getLogger(__name__)


class ConnectorSettingsMigration(StartupStep):
    """Moves what aios.yaml used to fix under `connectors.<name>.settings` onto the
    connector itself, then takes the section out of aios.yaml. A manifest's
    `x-locked` keeps such settings from agents now. Does nothing once moved."""

    def __init__(self, config: AiosYamlFile, connectors: Collection[Connector]) -> None:
        self._config = config
        self._connectors = connectors

    async def run(self) -> None:
        text = self._config.read()
        try:
            section = (yaml.safe_load(text) or {}).get("connectors")
        except yaml.YAMLError:
            return  # ai-os would not have started; nothing to do here
        if not section:
            return
        for name, entry in section.items():
            settings = (entry or {}).get("settings") or {}
            connector = self._connectors.get(name)
            if connector is None or not CodeConnectors.is_code(connector):
                log.warning("aios.yaml fixed settings of %s, which is no code connector", name)
                continue
            stored = CodeConnectors.stored(connector)
            merged = {**stored, **settings}
            if merged != stored:
                config = {**connector.config, SETTINGS_KEY: merged}
                await self._connectors.put(connector.model_copy(update={"config": config}))
            log.info("moved the settings aios.yaml fixed for %s onto the connector", name)
        text = ConfigYamlEditor().replace_section(text, "connectors", None)
        await self._config.write(text, "aios.yaml: connector settings moved onto the connectors")
