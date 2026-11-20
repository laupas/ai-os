import asyncio
from pathlib import Path

from aios.config.settings import CONFIG_FILE_NAME
from aios.config_repo.git_document_store import GitDocumentStore


class AiosYamlFile:
    """aios.yaml as the console reads and writes it: in the configuration
    repository when there is one, where every write is a commit, else the plain
    file ai-os was started with."""

    def __init__(self, config_file: Path, store: GitDocumentStore | None = None) -> None:
        self._config_file = Path(config_file)
        self._store = store

    def in_repository(self) -> bool:
        return self._store is not None and self._store.repo.exists()

    def read(self) -> str:
        if self.in_repository():
            return self._store.read_file(CONFIG_FILE_NAME) or ""  # type: ignore[union-attr]
        return self._config_file.read_text("utf-8") if self._config_file.exists() else ""

    async def write(self, text: str, message: str = f"{CONFIG_FILE_NAME}: update") -> None:
        if self.in_repository():
            await self._store.write_file(CONFIG_FILE_NAME, text, message)  # type: ignore[union-attr]
        else:
            await asyncio.to_thread(self._config_file.write_text, text, "utf-8")
