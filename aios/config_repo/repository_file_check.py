import json
import re
from pathlib import PurePosixPath
from typing import Any

import yaml
from pydantic import ValidationError

from aios.config.app_config import AppConfig
from aios.config.settings import CONFIG_FILE_NAME
from aios.config_repo.git_document_store import GitDocumentStore
from aios.connectors.code_connector_manifest import CodeConnectorManifest
from aios.storage.collection import Collection

PATH = re.compile(r"^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$")
PLACEHOLDER = "@@id@@"


class RepositoryFileCheck:
    """Says whether a file may be committed as it is, from where it lives: the
    configuration must still load after it, or ai-os would log the commit as
    unreadable and go on with the old configuration, which looks like the save
    did nothing.

    - `aios.yaml` against the model ai-os reads it with;
    - an agent, skill, connector, schedule or role through its collection's own
      layout and entity;
    - a code connector's `connector.yaml` against the manifest model;
    - Python by compiling it, other YAML and JSON by parsing them.
    """

    def __init__(self, store: GitDocumentStore, collections: list[Collection[Any]]) -> None:
        self._store = store
        self._collections = collections

    @staticmethod
    def path(path: str) -> str:
        """`path` if it may be written: inside the repository, never in `.git`."""
        parts = PurePosixPath(path).parts
        if not PATH.match(path) or ".." in parts or ".git" in parts:
            raise ValueError(f"not a path in the repository: {path!r}")
        return path

    def check(self, path: str, text: str) -> None:
        """Raises ValueError, saying what is wrong, when `text` may not be `path`."""
        self.path(path)
        try:
            self._check(path, text)
        except (ValidationError, yaml.YAMLError, json.JSONDecodeError, SyntaxError) as exc:
            raise ValueError(str(exc)) from exc

    def deletable(self, path: str) -> None:
        self.path(path)
        if path == CONFIG_FILE_NAME:
            raise ValueError("aios.yaml cannot be deleted; ai-os reads it at every start")

    def _check(self, path: str, text: str) -> None:
        if path == CONFIG_FILE_NAME:
            AppConfig.model_validate(yaml.safe_load(text) or {})
            return
        for collection in self._collections:
            doc_id = self._id_in(collection.name, path)
            if doc_id is not None:
                layout = self._store.layout(collection.name)
                collection.parse(layout.parse(text, doc_id))
                return
        parts = PurePosixPath(path).parts
        if len(parts) == 3 and parts[0] == "code" and parts[2] == "connector.yaml":
            data = yaml.safe_load(text) or {}
            if not isinstance(data, dict):
                raise ValueError("a manifest is a mapping")
            CodeConnectorManifest.model_validate({**data, "name": parts[1]})
            return
        suffix = PurePosixPath(path).suffix
        if suffix == ".py":
            compile(text, path, "exec", dont_inherit=True)
        elif suffix in (".yaml", ".yml"):
            yaml.safe_load(text)
        elif suffix == ".json":
            json.loads(text)

    def _id_in(self, collection: str, path: str) -> str | None:
        pattern = self._store.layout(collection).path(PLACEHOLDER)
        regex = re.escape(pattern).replace(re.escape(PLACEHOLDER), "([A-Za-z0-9][A-Za-z0-9_.-]*)")
        match = re.fullmatch(regex, path)
        return match.group(1) if match else None
