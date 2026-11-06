import asyncio
from typing import Any

from aios.config_repo.config_repo_watcher import ConfigRepoWatcher
from aios.config_repo.current_author import CurrentAuthor
from aios.config_repo.git_document_store import GitDocumentStore
from aios.config_repo.repository_conflict import RepositoryConflict
from aios.config_repo.repository_file_check import RepositoryFileCheck

BINARY_SNIFF = 8000


class RepositoryFiles:
    """The configuration repository as files, for the console: the tree of any
    branch, a file in it, its history, and writing one.

    A write is a commit in the caller's name, checked first so the configuration
    still loads, and refused when the file changed on the branch since it was
    opened (`base`, its blob id then). On the checked-out branch it takes the
    store's lock like every other write and is picked up at once; on another
    branch it is made beside, and applies when that branch is checked out or
    merged.
    """

    def __init__(
        self, store: GitDocumentStore, watcher: ConfigRepoWatcher, check: RepositoryFileCheck
    ) -> None:
        self._store = store
        self._repo = store.repo
        self._watcher = watcher
        self._check = check

    def current_branch(self) -> str:
        return self._repo.current_branch()

    async def tree(self, ref: str) -> list[dict]:
        await self._commit_of(ref)
        return await asyncio.to_thread(self._repo.tree, ref)

    async def read(self, ref: str, path: str) -> dict[str, Any]:
        await self._commit_of(ref)
        RepositoryFileCheck.path(path)
        blob = await asyncio.to_thread(self._repo.blob, ref, path)
        if blob is None:
            raise FileNotFoundError(path)
        text = await asyncio.to_thread(self._repo.show, ref, path) or ""
        binary = "\0" in text[:BINARY_SNIFF]
        return {"path": path, "blob": blob, "text": None if binary else text, "binary": binary}

    async def history(self, ref: str, path: str | None, skip: int, limit: int) -> list[dict]:
        await self._commit_of(ref)
        if path:
            RepositoryFileCheck.path(path)
        return await asyncio.to_thread(self._repo.changes, limit, ref, path, skip)

    async def diff(self, commit: str) -> str:
        await self._commit_of(commit)
        return await asyncio.to_thread(self._repo.diff, commit, ".")

    async def write(
        self, branch: str, path: str, text: str | None, base: str | None, message: str
    ) -> str | None:
        """Commits `text` as `path` on `branch`, or removes it when `text` is None.
        `base` is the blob id it was opened at, None for a new file. Returns the
        commit, or None when nothing changed."""
        if text is None:
            self._check.deletable(path)
        else:
            self._check.check(path, text)
        if branch not in {b["name"] for b in await asyncio.to_thread(self._repo.branches)}:
            raise ValueError(f"no branch called {branch}")
        message = message.strip() or f"{path}: {'delete' if text is None else 'update'}"
        author = CurrentAuthor.get()
        async with self._store.lock:
            now = await asyncio.to_thread(self._repo.blob, branch, path)
            if now != base:
                raise RepositoryConflict(
                    f"{path} changed on {branch} since it was opened" if base else f"{path} exists"
                )
            if branch == await asyncio.to_thread(self._repo.current_branch):
                commit = await asyncio.to_thread(self._write_here, path, text, message, author)
            else:
                commit = await asyncio.to_thread(
                    self._repo.commit_on, branch, {path: text}, message, author
                )
        if commit is not None:
            # Loaded now rather than at the watcher's next look, and auto-push told.
            await self._watcher.check()
            await self._store.committed()
        return commit

    def _write_here(self, path: str, text: str | None, message: str, author) -> str | None:  # type: ignore[no-untyped-def]
        file = self._repo.root / path
        if text is None:
            file.unlink(missing_ok=True)
        else:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text, encoding="utf-8")
        return self._repo.commit([path], message, author)

    async def _commit_of(self, ref: str) -> str:
        commit = await asyncio.to_thread(self._repo.resolve, ref)
        if commit is None:
            raise ValueError(f"no branch or commit {ref!r}")
        return commit
