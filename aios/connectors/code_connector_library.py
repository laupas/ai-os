import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from aios.connectors.code_connector_manifest import CodeConnectorManifest
from aios.storage.storage_name import StorageName

log = logging.getLogger(__name__)

MANIFEST = "connector.yaml"


class CodeConnectorLibrary:
    """The code connectors there are: one folder each, holding `connector.yaml` and
    its server, under any of `roots` (those shipped with ai-os, and those an
    administrator put in the configuration repository). Read on every call, so a
    folder added on the host is there without a restart.

    Agents cannot write here: the `config_*` tools write agents, skills and
    connector configs, never files of their own choosing.
    """

    def __init__(self, roots: list[Path]) -> None:
        self._roots = [Path(r) for r in roots]

    def all(self) -> list[CodeConnectorManifest]:
        found: dict[str, CodeConnectorManifest] = {}
        for root in self._roots:
            for file in sorted(root.glob(f"*/{MANIFEST}")) if root.is_dir() else []:
                manifest = self._load(file)
                if manifest is not None:
                    found.setdefault(manifest.name, manifest)  # earlier roots win
        return sorted(found.values(), key=lambda m: m.name)

    def get(self, name: str) -> CodeConnectorManifest | None:
        return next((m for m in self.all() if m.name == name), None)

    @staticmethod
    def _load(file: Path) -> CodeConnectorManifest | None:
        folder = file.parent
        try:
            data = yaml.safe_load(file.read_text("utf-8")) or {}
            manifest = CodeConnectorManifest.model_validate(
                {**data, "name": StorageName.check(folder.name), "folder": folder}
            )
        except (OSError, yaml.YAMLError, ValidationError, ValueError) as exc:
            log.warning("code connector %s is unreadable: %s", folder, exc)
            return None
        if not manifest.server_path.resolve().is_relative_to(folder.resolve()):
            log.warning("code connector %s: its server is outside its folder", folder)
            return None
        return manifest
