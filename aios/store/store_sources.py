import asyncio
import hashlib
import logging
import os
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from aios.config.store_source import StoreSource
from aios.config_repo.git_repository import GitRepository
from aios.store.store_item import StoreItem
from aios.store.store_listing import StoreListing
from aios.store.store_ref import StoreRef
from aios.store.store_source_reader import StoreSourceReader

log = logging.getLogger(__name__)

NO_PROMPT = {"GIT_TERMINAL_PROMPT": "0"}
"""A source that wants a password fails instead of waiting for one."""


class StoreSources:
    """The sources in aios.yaml, each a shallow clone under `root`. A source is
    fetched the first time it is listed and again on `refresh`; a fetch goes into
    a new folder that replaces the old one only once it worked, so a source that
    cannot be reached keeps offering what it last had."""

    def __init__(
        self,
        root: Path,
        sources: Callable[[], list[StoreSource]],
        reader: StoreSourceReader,
    ) -> None:
        self._root = Path(root)
        self._sources = sources
        self._reader = reader
        self._errors: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def listings(self, refresh: bool = False) -> list[StoreListing]:
        async with self._lock:
            listings = []
            for source in self._sources():
                folder = self.folder_of(source)
                if refresh or not folder.is_dir():
                    await self._fetch(source, folder)
                listings.append(await asyncio.to_thread(self._read, source, folder))
            return listings

    async def fetched(self) -> list[StoreListing]:
        """What the sources offered when last fetched; never fetches, so a page
        that only shows versions does not wait for the network."""
        return [
            await asyncio.to_thread(self._read, source, self.folder_of(source))
            for source in self._sources()
        ]

    async def find(self, url: str, ref: StoreRef) -> tuple[StoreListing, StoreItem] | None:
        for listing in await self.listings():
            if listing.url == url:
                item = listing.get(ref)
                return (listing, item) if item else None
        return None

    def folder_of(self, source: StoreSource) -> Path:
        key = f"{source.url}#{source.branch or ''}"
        return self._root / hashlib.sha256(key.encode()).hexdigest()[:16]

    async def _fetch(self, source: StoreSource, folder: Path) -> None:
        fresh = folder.with_name(folder.name + ".new")
        try:
            await asyncio.to_thread(shutil.rmtree, fresh, True)
            repo = GitRepository(fresh)
            await asyncio.to_thread(repo.clone, source.url, NO_PROMPT, source.branch, True)
            await asyncio.to_thread(self._swap, fresh, folder)
            self._errors.pop(source.url, None)
            log.info("store: fetched %s", source.url)
        except (OSError, RuntimeError, TimeoutError) as exc:
            await asyncio.to_thread(shutil.rmtree, fresh, True)
            self._errors[source.url] = str(exc)
            log.warning("store: cannot fetch %s: %s", source.url, exc)

    def _read(self, source: StoreSource, folder: Path) -> StoreListing:
        listing = StoreListing(
            url=source.url, branch=source.branch, error=self._errors.get(source.url)
        )
        if not folder.is_dir():
            return listing
        fetched = datetime.fromtimestamp(folder.stat().st_mtime, UTC)
        return self._reader.read(folder, listing.model_copy(update={"fetched_at": fetched}))

    @staticmethod
    def _swap(fresh: Path, folder: Path) -> None:
        old = folder.with_name(folder.name + ".old")
        shutil.rmtree(old, ignore_errors=True)
        if folder.exists():
            folder.rename(old)
        fresh.rename(folder)
        os.utime(folder)  # when it was fetched, which a rename does not record
        shutil.rmtree(old, ignore_errors=True)
