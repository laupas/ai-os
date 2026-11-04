from pathlib import Path
from typing import Any

import yaml

from aios.config_repo.file_layout import FileLayout


class YamlLayout(FileLayout):
    """One YAML file per document: `<directory>/<id>.yaml`. For short settings
    (a connector, a schedule) that have no long text to read as Markdown."""

    def __init__(self, directory: str) -> None:
        self._dir = directory

    def path(self, doc_id: str) -> str:
        return f"{self._dir}/{doc_id}.yaml"

    def ids(self, root: Path) -> list[str]:
        return sorted(p.stem for p in (root / self._dir).glob("*.yaml") if p.is_file())

    def render(self, doc: dict[str, Any]) -> str:
        data = {k: v for k, v in doc.items() if k != "id"}
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000)

    def parse(self, text: str, doc_id: str) -> dict[str, Any]:
        return {**(yaml.safe_load(text) or {}), "id": doc_id}
