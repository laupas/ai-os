import logging
from pathlib import Path

import yaml

from aios.config.app_config import AppConfig

log = logging.getLogger(__name__)


class AppConfigLoader:
    """Reads config.yaml; a missing file means all defaults.

    `${VAR}` references inside `mcp_servers` are kept as written: they are copied
    into the connectors once and expanded only when a server is started.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def load(self) -> AppConfig:
        if not self._path.exists():
            log.info("no config file at %s, using defaults", self._path)
            return AppConfig()
        data = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        return AppConfig.model_validate(data)
