import logging

import yaml
from pydantic import ValidationError

from aios.config.app_config import AppConfig

log = logging.getLogger(__name__)

STARTUP_ONLY = {"channels", "web", "collection_access", "owner", "connectors", "mcp_servers"}
"""Sections read once, while ai-os starts: a change needs a restart. Every other
section is read where it is used, and a saved aios.yaml applies within seconds."""


class LiveAppConfig:
    """aios.yaml as it is now. `current()` is what the running parts read on each
    use; `started_with()` is what the startup-only sections were built from.

    A file that does not parse is logged and the previous configuration stays.
    """

    def __init__(self, config: AppConfig) -> None:
        self._started = config
        self._current = config

    def current(self) -> AppConfig:
        return self._current

    def started_with(self) -> AppConfig:
        return self._started

    def apply(self, text: str) -> bool:
        """Takes `text` as the new aios.yaml; returns whether anything changed."""
        try:
            config = AppConfig.model_validate(yaml.safe_load(text) or {})
        except (yaml.YAMLError, ValidationError) as exc:
            log.error("aios.yaml does not load, keeping the previous one: %s", exc)
            return False
        if config == self._current:
            return False
        changed = [
            key
            for key in AppConfig.model_fields
            if getattr(config, key) != getattr(self._current, key)
        ]
        self._current = config
        later = [key for key in changed if key in STARTUP_ONLY]
        log.info(
            "aios.yaml applied: %s%s",
            ", ".join(changed),
            f" ({', '.join(later)} after a restart)" if later else "",
        )
        return True

    def restart_needed(self, text: str) -> bool:
        """Whether `text` differs from what ai-os started with in a section that is
        read only at startup. A file that does not parse cannot be applied either way."""
        try:
            config = AppConfig.model_validate(yaml.safe_load(text) or {})
        except (yaml.YAMLError, ValidationError):
            return True
        return any(getattr(config, key) != getattr(self._started, key) for key in STARTUP_ONLY)
