import asyncio
import logging
import re
from typing import Any

from aios.config_repo.branch_error import BranchError
from aios.config_repo.current_author import CurrentAuthor
from aios.config_repo.git_document_store import GitDocumentStore
from aios.storage.collection import Collection

log = logging.getLogger(__name__)

NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,60}(/[A-Za-z0-9][A-Za-z0-9._-]{0,60})?$")
PROTECTED = "main"


class ConfigBranches:
    """Branches of the configuration repository: several versions of the agents,
    skills, connectors and schedules side by side.

    The checked-out branch is the one ai-os runs; switching reloads the
    configuration at once. A merge into another branch happens in a temporary
    worktree, so it never changes what is running; a conflicting merge is undone
    and its files named. Every operation holds the store's lock, so no save can
    land halfway through a switch.
    """

    def __init__(self, store: GitDocumentStore, collections: list[Collection[Any]]) -> None:
        self._store = store
        self._repo = store.repo
        self._collections = collections

    async def overview(self) -> dict[str, Any]:
        def read() -> dict[str, Any]:
            current = self._repo.current_branch()
            rows = []
            for branch in self._repo.branches():
                ahead, behind = (0, 0)
                if branch["name"] != current:
                    ahead, behind = self._repo.ahead_behind(branch["name"], current)
                rows.append(
                    {
                        **branch,
                        "current": branch["name"] == current,
                        "ahead": ahead,
                        "behind": behind,
                    }
                )
            return {
                "current": current,
                "protected": PROTECTED,
                "branches": rows,
                "clean": self._repo.is_clean(),
            }

        return await asyncio.to_thread(read)

    async def create(self, name: str, start: str | None) -> None:
        self._check_name(name)
        async with self._store.lock:
            existing = {b["name"] for b in await asyncio.to_thread(self._repo.branches)}
            if name in existing:
                raise BranchError(f"there is already a branch called {name}")
            origin = start or await asyncio.to_thread(self._repo.current_branch)
            if origin not in existing:
                raise BranchError(f"no branch called {origin}")
            await asyncio.to_thread(self._repo.create_branch, name, origin)
        log.info("branch %s created from %s", name, origin)
        await self._store.committed()

    async def switch(self, name: str) -> None:
        async with self._store.lock:
            await self._known(name)
            if not await asyncio.to_thread(self._repo.is_clean):
                raise BranchError(
                    "there are uncommitted edits in the repository; commit them first"
                )
            await asyncio.to_thread(self._repo.checkout, name)
            await self._reload()
        log.info("switched the configuration to branch %s", name)

    async def merge(self, source: str, target: str) -> list[str]:
        """Returns the conflicting files; empty when merged."""
        if source == target:
            raise BranchError("a branch cannot be merged into itself")
        async with self._store.lock:
            await self._known(source)
            await self._known(target)
            current = await asyncio.to_thread(self._repo.current_branch)
            if target == current and not await asyncio.to_thread(self._repo.is_clean):
                raise BranchError(
                    "there are uncommitted edits in the repository; commit them first"
                )
            conflicts = await asyncio.to_thread(
                self._repo.merge,
                source,
                target,
                f"Merge {source} into {target}",
                CurrentAuthor.get(),
            )
            if not conflicts and target == current:
                await self._reload()
        if not conflicts:
            log.info("merged %s into %s", source, target)
            await self._store.committed()
        return conflicts

    async def delete(self, name: str, force: bool) -> None:
        if name == PROTECTED:
            raise BranchError(f"{PROTECTED} cannot be deleted")
        async with self._store.lock:
            await self._known(name)
            if name == await asyncio.to_thread(self._repo.current_branch):
                raise BranchError("the branch ai-os runs cannot be deleted; switch away first")
            try:
                await asyncio.to_thread(self._repo.delete_branch, name, force)
            except RuntimeError as exc:
                raise BranchError(
                    f"{name} has changes that are on no other branch; "
                    "merge it first, or delete it anyway"
                ) from exc

    async def compare(self, name: str) -> dict[str, Any]:
        await self._known(name)
        current = await asyncio.to_thread(self._repo.current_branch)
        files = await asyncio.to_thread(self._repo.changed_files, name, current)
        return {"branch": name, "base": current, "files": files}

    async def _reload(self) -> None:
        for collection in self._collections:
            await collection.load()
        self._store.last_head = await asyncio.to_thread(self._repo.head)

    async def _known(self, name: str) -> None:
        names = {b["name"] for b in await asyncio.to_thread(self._repo.branches)}
        if name not in names:
            raise BranchError(f"no branch called {name}")

    @staticmethod
    def _check_name(name: str) -> None:
        if not NAME.match(name) or ".." in name or name.endswith(".lock"):
            raise BranchError("a branch name is letters, digits, . _ - and at most one /")
