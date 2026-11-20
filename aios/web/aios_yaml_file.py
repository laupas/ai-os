import asyncio
from pathlib import Path

from aios.config.live_app_config import LiveAppConfig
from aios.config.settings import CONFIG_FILE_NAME
from aios.config_repo.git_document_store import GitDocumentStore


class AiosYamlFile:
    """aios.yaml as the console reads and writes it: in the configuration
    repository when there is one, where every write is a commit, else the plain
    file ai-os was started with. A write applies to the running ai-os at once."""

    def __init__(
        self,
        config_file: Path,
        store: GitDocumentStore | None = None,
        live: LiveAppConfig | None = None,
    ) -> None:
        self._config_file = Path(config_file)
        self._store = store
        self._live = live

    def in_repository(self) -> bool:
        return self._store is not None and self._store.repo.exists()

    def read(self) -> str:
        if self.in_repository():
            return self._store.read_file(CONFIG_FILE_NAME) or ""  # type: ignore[union-attr]
        return self._config_file.read_text("utf-8") if self._config_file.exists() else ""

    def read_committed(self) -> str | None:
        """As it counts for the running ai-os: in the repository, the file as
        committed, since an edit in the working tree is somebody's work in progress."""
        if self.in_repository():
            return self._store.repo.show("HEAD", CONFIG_FILE_NAME)  # type: ignore[union-attr]
        return self._config_file.read_text("utf-8") if self._config_file.exists() else None

    async def write(self, text: str, message: str = f"{CONFIG_FILE_NAME}: update") -> None:
        if self.in_repository():
            await self._store.write_file(CONFIG_FILE_NAME, text, message)  # type: ignore[union-attr]
        else:
            await asyncio.to_thread(self._config_file.write_text, text, "utf-8")
        if self._live is not None:
            self._live.apply(text)
