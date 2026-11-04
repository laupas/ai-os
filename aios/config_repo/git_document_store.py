from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import yaml

from aios.config_repo.current_author import CurrentAuthor
from aios.config_repo.file_layout import FileLayout
from aios.config_repo.git_repository import GitRepository
from aios.storage.document_store import DocumentStore
from aios.storage.storage_name import StorageName

log = logging.getLogger(__name__)

FILE = re.compile(r"^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$")


class GitDocumentStore(DocumentStore):
    """The configuration collections (agents, skills, connectors, schedules) as
    files in a git repository, with one commit per change.

    A commit is attributed to `CurrentAuthor`: the console user, or ai-os. Fields
    that change at runtime (a schedule's `last_fired_at`) are kept in `state`
    instead, so a schedule firing does not make a commit. A failing git command is
    logged and never fails the save: the file is the data, the commit its history.
    """

    def __init__(
        self,
        repo: GitRepository,
        layouts: dict[str, FileLayout],
        state: DocumentStore,
        runtime_fields: dict[str, list[str]] | None = None,
    ) -> None:
        self._repo = repo
        self._layouts = layouts
        self._state = state
        self._runtime = runtime_fields or {}
        self._lock = asyncio.Lock()
        self._batch: list[str] | None = None
        self._listeners: list[Callable[[], Awaitable[None]]] = []
        self.last_head: str | None = None
        """The head this process last wrote or read: another one means an outside commit."""

    @property
    def repo(self) -> GitRepository:
        return self._repo

    def on_commit(self, listener: Callable[[], Awaitable[None]]) -> None:
        """Called after every commit this store makes (auto-push listens)."""
        self._listeners.append(listener)

    @property
    def lock(self) -> asyncio.Lock:
        """Held for every write; branch operations take it too."""
        return self._lock

    def path_of(self, collection: str, doc_id: str) -> str:
        return self.layout(collection).path(StorageName.check(doc_id))

    async def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        file = self._repo.root / self.path_of(collection, doc_id)
        text = await asyncio.to_thread(self._read, file)
        if text is None:
            return None
        return await self._with_state(collection, self.layout(collection).parse(text, doc_id))

    async def put(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        layout = self.layout(collection)
        runtime = {k: data[k] for k in self._runtime.get(collection, []) if k in data}
        if runtime:
            await self._state.put(self._state_name(collection), doc_id, {"id": doc_id, **runtime})
        config = {k: v for k, v in data.items() if k not in runtime}
        path = self.path_of(collection, doc_id)
        text = layout.render(config)
        async with self._lock:
            file = self._repo.root / path
            before = await asyncio.to_thread(self._read, file)
            if before == text:
                return
            await asyncio.to_thread(self._write, file, text)
            verb = "add" if before is None else "update"
            await self._commit([path], f"{collection}/{doc_id}: {verb}")

    async def delete(self, collection: str, doc_id: str) -> None:
        path = self.path_of(collection, doc_id)
        if self._runtime.get(collection):
            await self._state.delete(self._state_name(collection), doc_id)
        async with self._lock:
            file = self._repo.root / path
            if not file.exists():
                return
            await asyncio.to_thread(self._remove, file, self._repo.root)
            await self._commit([path], f"{collection}/{doc_id}: delete")

    async def list(self, collection: str) -> list[dict[str, Any]]:
        documents, _ = await self._read_all(collection)
        return documents

    async def unreadable(self, collection: str) -> list[str]:
        """The files of `collection` that do not parse, to refuse a reload over them."""
        _, bad = await self._read_all(collection)
        return bad

    async def _read_all(self, collection: str) -> tuple[list[dict[str, Any]], list[str]]:
        layout = self.layout(collection)
        documents, bad = [], []
        for doc_id in await asyncio.to_thread(layout.ids, self._repo.root):
            path = layout.path(doc_id)
            text = await asyncio.to_thread(self._read, self._repo.root / path)
            try:
                documents.append(
                    await self._with_state(collection, layout.parse(text or "", doc_id))
                )
            except (yaml.YAMLError, ValueError) as exc:
                log.error("skipping unreadable %s: %s", path, exc)
                bad.append(path)
        return documents, bad

    async def write_file(self, path: str, text: str, message: str) -> bool:
        """A file that is no collection's document (`aios.yaml`), committed like one.
        Returns whether anything changed."""
        self._check_file(path)
        async with self._lock:
            file = self._repo.root / path
            if await asyncio.to_thread(self._read, file) == text:
                return False
            await asyncio.to_thread(self._write, file, text)
            await self._commit([path], message)
        return True

    def read_file(self, path: str) -> str | None:
        return self._read(self._repo.root / self._check_file(path))

    @staticmethod
    def _check_file(path: str) -> str:
        if not FILE.match(path) or ".." in path:
            raise ValueError(f"invalid file name: {path!r}")
        return path

    @asynccontextmanager
    async def batch(self, message: str) -> AsyncIterator[None]:
        """Every write inside goes into one commit, made at the end."""
        self._batch = []
        try:
            yield
        finally:
            paths, self._batch = self._batch, None
            if paths:
                await self._commit(paths, message)

    def layout(self, collection: str) -> FileLayout:
        layout = self._layouts.get(collection)
        if layout is None:
            raise ValueError(f"{collection} is not kept in the configuration repository")
        return layout

    async def _commit(self, paths: list[str], message: str) -> None:
        if self._batch is not None:
            self._batch.extend(paths)
            return
        try:
            head = await asyncio.to_thread(self._repo.commit, paths, message, CurrentAuthor.get())
        except Exception:
            log.exception("could not commit %s", message)
            return
        if head is not None:
            self.last_head = head
            await self.committed()

    async def committed(self) -> None:
        """Tells the listeners the repository changed: after a commit here, or a
        merge or new branch made beside this store."""
        for listener in self._listeners:
            try:
                await listener()
            except Exception:
                log.exception("a commit listener failed")

    async def _with_state(self, collection: str, doc: dict[str, Any]) -> dict[str, Any]:
        if not self._runtime.get(collection):
            return doc
        state = await self._state.get(self._state_name(collection), doc["id"]) or {}
        return {**doc, **{k: v for k, v in state.items() if k != "id"}}

    @staticmethod
    def _state_name(collection: str) -> str:
        return f"{collection}-state"

    @staticmethod
    def _read(file: Path) -> str | None:
        return file.read_text(encoding="utf-8") if file.is_file() else None

    @staticmethod
    def _write(file: Path, text: str) -> None:
        file.parent.mkdir(parents=True, exist_ok=True)
        tmp = file.with_name(f".{file.name}.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(file)

    @staticmethod
    def _remove(file: Path, root: Path) -> None:
        file.unlink()
        # A skill is a folder of its own: do not leave it behind empty.
        if file.parent != root and not any(file.parent.iterdir()):
            file.parent.rmdir()
