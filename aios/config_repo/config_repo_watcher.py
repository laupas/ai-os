import asyncio
import logging
from typing import Any

from aios.bootstrap.background_service import BackgroundService
from aios.config_repo.git_document_store import GitDocumentStore
from aios.storage.collection import Collection

log = logging.getLogger(__name__)


class ConfigRepoWatcher(BackgroundService):
    """Picks up commits made outside ai-os (Claude Code, a terminal) by reloading
    the configuration collections when the repository's head moves.

    Only commits count: an edit still in the working tree is somebody's work in
    progress. A commit that does not load (a typo in a front matter) is logged and
    the previous configuration stays in use.
    """

    def __init__(
        self,
        store: GitDocumentStore,
        collections: list[Collection[Any]],
        interval_seconds: float = 5,
    ) -> None:
        self._store = store
        self._collections = collections
        self._interval = interval_seconds

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            await self.check()

    async def check(self) -> None:
        head = await asyncio.to_thread(self._store.repo.head)
        if head is None or head == self._store.last_head:
            return
        self._store.last_head = head  # once per commit, even if it does not load
        for collection in self._collections:
            if bad := await self._store.unreadable(collection.name):
                log.error(
                    "commit %s has unreadable files (%s); keeping the previous configuration",
                    head[:8],
                    ", ".join(bad),
                )
                return
        try:
            for collection in self._collections:
                await collection.load()
        except Exception:
            log.exception("commit %s does not load; keeping the previous configuration", head[:8])
            return
        log.info("picked up configuration commit %s", head[:8])
