import asyncio
from datetime import UTC, datetime
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

    async def remote(self, branch: str) -> dict[str, Any]:
        """How `branch` stands against the remote, as of the last fetch: whether
        there is a remote, whether the branch is on it, the local commits not
        pushed yet and how many of the remote's are not pulled."""
        if branch not in {b["name"] for b in await asyncio.to_thread(self._repo.branches)}:
            raise ValueError(f"no branch called {branch}")
        url = await asyncio.to_thread(self._repo.remote_url)
        if url is None:
            return {"configured": False}
        unpushed = await asyncio.to_thread(self._repo.unpushed, branch)
        counts = await asyncio.to_thread(self._repo.remote_ahead_behind, branch)
        fetched = await asyncio.to_thread(self._repo.fetched_at)
        return {
            "configured": True,
            "on_remote": unpushed is not None,
            "unpushed": unpushed or [],
            "behind": counts[1] if counts else 0,
            "fetched_at": datetime.fromtimestamp(fetched, UTC).isoformat() if fetched else None,
        }

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

    async def undo(self, branch: str, commit: str) -> str | None:
        """Undoes one commit of `branch` with a new commit; the commits after it
        stay. Returns the new commit, or None when there was nothing left to undo."""
        author = CurrentAuthor.get()
        return await self._replace(
            branch, commit, lambda tip, full: self._repo.revert(tip, full, author)
        )

    async def restore(self, branch: str, commit: str) -> str | None:
        """Brings every file of `branch` back to how it was at `commit`, with a new
        commit: nothing in between is lost, and a push stays a plain push. Returns
        the new commit, or None when the branch already is that way."""
        author = CurrentAuthor.get()
        return await self._replace(
            branch,
            commit,
            lambda tip, full: self._repo.restore(
                tip, full, f"Restore {branch} as of {full[:7]}", author
            ),
        )

    async def _replace(self, branch: str, commit: str, make) -> str | None:  # type: ignore[no-untyped-def]
        """Makes a commit on top of `branch` with `make(tip, commit)` beside it,
        checks every file it changes as a save would be checked, and only then
        moves the branch."""
        if branch not in {b["name"] for b in await asyncio.to_thread(self._repo.branches)}:
            raise ValueError(f"no branch called {branch}")
        full = await self._commit_of(commit)
        async with self._store.lock:
            tip = await self._commit_of(branch)
            if not await asyncio.to_thread(self._repo.is_ancestor, full, tip):
                raise ValueError(f"{commit[:7]} is not in the history of {branch}")
            running = branch == await asyncio.to_thread(self._repo.current_branch)
            if running and not await asyncio.to_thread(self._repo.is_clean):
                raise RepositoryConflict(
                    "there are uncommitted edits in the repository; commit them first"
                )
            new = await asyncio.to_thread(make, tip, full)
            if new is None:
                return None
            await asyncio.to_thread(self._check_commit, tip, new)
            await asyncio.to_thread(self._repo.advance, branch, tip, new)
        await self._watcher.check()
        await self._store.committed()
        return new

    def _check_commit(self, old: str, new: str) -> None:
        for row in self._repo.changed_files(new, old):
            path = row["path"]
            if row["status"] == "D":
                self._check.deletable(path)
                continue
            text = self._repo.show(new, path) or ""
            if "\0" not in text[:BINARY_SNIFF]:
                try:
                    self._check.check(path, text)
                except ValueError as exc:
                    raise ValueError(f"{path} would no longer load: {exc}") from exc

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
