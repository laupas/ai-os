import asyncio
import logging
from pathlib import Path
from typing import Any

from aios.agents.repo_agent_reader import RepoAgentReader
from aios.agents.repo_skill_reader import RepoSkillReader
from aios.bootstrap.startup_step import StartupStep
from aios.config.settings import CONFIG_FILE_NAME
from aios.config_repo.git_document_store import GitDocumentStore
from aios.storage.collection import Collection
from aios.storage.document_store import DocumentStore

log = logging.getLogger(__name__)


MARKER = ".aios-imported"
EARLIER_IMPORTS = {"agents", "skills", "connectors", "schedules"}
"""What a repository made before the marker existed had already imported."""


class ConfigRepoInitializer(StartupStep):
    """Creates the configuration repository on the first start, in one commit, and
    later imports any kind of configuration that moved into it since.

    Each kind comes from where it lived before, if anywhere: the per-document JSON
    files of an earlier version, else (only for a new repository) the seed: the
    repo's `agents/` and `skills/`, `mcp_servers` from config.yaml. A new repository
    also takes the data dir's `config.yaml` as `aios.yaml`. `.aios-imported` records
    what was imported, so a kind emptied on purpose is never filled again.
    """

    def __init__(
        self,
        store: GitDocumentStore,
        legacy: DocumentStore,
        collections: list[Collection[Any]],
        agent_reader: RepoAgentReader,
        skill_reader: RepoSkillReader,
        mcp_servers: dict[str, dict[str, Any]],
        legacy_config: Path | None = None,
    ) -> None:
        self._store = store
        self._legacy = legacy
        self._collections = collections
        self._agent_reader = agent_reader
        self._skill_reader = skill_reader
        self._mcp_servers = mcp_servers
        self._legacy_config = legacy_config

    async def run(self) -> None:
        repo = self._store.repo
        fresh = not await asyncio.to_thread(repo.exists)
        if fresh:
            await asyncio.to_thread(repo.init)
        imported = self._imported(fresh)
        todo = [c for c in self._collections if c.name not in imported]
        if todo or fresh:
            message = (
                "Configuration repository created"
                if fresh
                else "Imported " + ", ".join(c.name for c in todo)
            )
            async with self._store.batch(message):
                for collection in todo:
                    await self._import(collection, fresh)
                if fresh:
                    await self._take_config_file()
                names = sorted(imported | {c.name for c in self._collections})
                await self._store.write_file(MARKER, "\n".join(names) + "\n", "")
            for collection in self._collections:
                await collection.load()
            log.info("%s at %s", message, repo.root)
        self._store.last_head = await asyncio.to_thread(repo.head)

    def _imported(self, fresh: bool) -> set[str]:
        if fresh:
            return set()
        text = self._store.read_file(MARKER)
        return set(text.split()) if text is not None else set(EARLIER_IMPORTS)

    async def _import(self, collection: Collection[Any], fresh: bool) -> None:
        seeds = {
            "agents": lambda: [a.model_dump(mode="json") for a in self._agent_reader.read()],
            "skills": lambda: [s.model_dump(mode="json") for s in self._skill_reader.read()],
            "connectors": lambda: [
                {"id": name, "description": "", "config": config, "enabled": True}
                for name, config in self._mcp_servers.items()
            ],
        }
        documents = await self._legacy.list(collection.name)
        origin = f"{collection.name}/ in the data dir"
        if not documents and fresh and collection.name in seeds:
            documents, origin = seeds[collection.name](), "the seed"
        for document in documents:
            # Through the model, so an older document's shape is brought up to date
            # here, in this commit, not in the first later save.
            item = collection.parse(document).model_dump(mode="json")
            await self._store.put(collection.name, item["id"], item)
        log.info("%s: %d from %s", collection.name, len(documents), origin)

    async def _take_config_file(self) -> None:
        if self._legacy_config is None or not self._legacy_config.exists():
            return
        text = await asyncio.to_thread(self._legacy_config.read_text, encoding="utf-8")
        await self._store.write_file(CONFIG_FILE_NAME, text, "")
        await asyncio.to_thread(
            self._legacy_config.rename,
            self._legacy_config.with_name("config.yaml.moved-to-repository"),
        )
