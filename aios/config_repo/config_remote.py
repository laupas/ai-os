import asyncio
import logging
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aios.common.clock import Clock
from aios.config_repo.branch_error import BranchError
from aios.config_repo.current_author import CurrentAuthor
from aios.config_repo.git_credentials import GitCredentials
from aios.config_repo.git_document_store import GitDocumentStore
from aios.config_repo.remote_result import RemoteResult
from aios.entities.git.git_remote import GitRemote
from aios.storage.collection import Collection
from aios.variables.secret_box import SecretBox

log = logging.getLogger(__name__)

URL = re.compile(r"^(https://[^\s]+|[A-Za-z0-9._-]+@[A-Za-z0-9.-]+:[^\s]+|ssh://[^\s]+)$")
AUTO_PUSH_DELAY = 3.0


class ConfigRemote:
    """The configuration repository's remote: where it is, how ai-os signs in, and
    pushing, fetching and pulling.

    Signing in is an SSH key ai-os generates (its public half goes to the server, a
    GitHub deploy key with write access) or a token (a GitHub token with access to
    that one repository). Both are stored encrypted and only ever handed to one git
    command: the key as a temporary file, the token as an HTTP header through git's
    environment, so neither is written to the repository's config nor shows up in a
    process list. With auto-push, every commit is pushed a few seconds later, which
    is the off-site copy of the configuration.
    """

    def __init__(
        self,
        store: GitDocumentStore,
        remotes: Collection[GitRemote],
        box: SecretBox,
        clock: Clock,
        known_hosts: Path,
        collections: list[Collection[Any]],
    ) -> None:
        self._store = store
        self._repo = store.repo
        self._remotes = remotes
        self._box = box
        self._clock = clock
        self._known_hosts = Path(known_hosts)
        self._collections = collections
        self._pending: asyncio.Task[None] | None = None
        self.last: RemoteResult | None = None
        store.on_commit(self._after_commit)

    def settings(self) -> GitRemote | None:
        return self._remotes.get("origin")

    async def save(
        self, url: str, auth: str, token: str | None, auto_push: bool, author: str
    ) -> GitRemote:
        if not URL.match(url):
            raise BranchError("give the repository's https or ssh address")
        current = self.settings()
        stored_token = current.token if current else None
        if token:
            stored_token = self._box.encrypt(token)
        if auth == "token" and not stored_token:
            raise BranchError("a token is needed to sign in with one")
        if auth == "token" and not url.startswith("https://"):
            raise BranchError("a token works with an https address; use an SSH key for git@…")
        if auth == "ssh" and url.startswith("https://"):
            raise BranchError(
                "an SSH key works with an ssh address (git@github.com:owner/repo.git)"
            )
        remote = GitRemote(
            url=url,
            auth=auth,  # type: ignore[arg-type]
            public_key=current.public_key if current else None,
            private_key=current.private_key if current else None,
            token=stored_token,
            auto_push=auto_push,
            updated_at=self._clock.now(),
            updated_by=author,
        )
        await self._remotes.put(remote)
        await asyncio.to_thread(self._repo.set_remote, url)
        return remote

    async def generate_key(self, author: str) -> str:
        """A new SSH key pair; returns the public half to give the server. The
        private half is never shown."""
        key = Ed25519PrivateKey.generate()
        private = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            serialization.NoEncryption(),
        ).decode()
        public = (
            key.public_key()
            .public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
            .decode()
            + " ai-os"
        )
        current = self.settings()
        base = current or GitRemote(url="", auth="ssh")
        await self._remotes.put(
            base.model_copy(
                update={
                    "public_key": public,
                    "private_key": self._box.encrypt(private),
                    "updated_at": self._clock.now(),
                    "updated_by": author,
                }
            )
        )
        return public

    async def adopt(self, url: str, ssh_key: str | None, token: str | None) -> None:
        """Takes over the remote a fresh install was cloned from (`AIOS_CONFIG_*`),
        so the console shows it and auto-push carries on. A remote already set up in
        the console is left alone."""
        if self.settings() is not None or not url:
            return
        public = None
        if ssh_key:
            loaded = serialization.load_ssh_private_key(ssh_key.strip().encode() + b"\n", None)
            public = (
                loaded.public_key()
                .public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
                .decode()
                + " ai-os"
            )
        await self._remotes.put(
            GitRemote(
                url=url,
                auth="token" if token else "ssh" if ssh_key else "none",
                public_key=public,
                private_key=self._box.encrypt(ssh_key) if ssh_key else None,
                token=self._box.encrypt(token) if token else None,
                auto_push=True,
                updated_at=self._clock.now(),
                updated_by="restored from the environment",
            )
        )
        log.info("took over the configuration remote %s from the environment", url)

    async def remove(self) -> None:
        await self._remotes.delete("origin")
        await asyncio.to_thread(self._repo.remove_remote)

    async def test(self) -> RemoteResult:
        return await self._run("test", lambda env: self._repo.ls_remote(env) or "connected; empty")

    async def fetch(self) -> RemoteResult:
        return await self._run("fetch", lambda env: self._repo.fetch(env) or "fetched")

    async def push(self, branch: str | None) -> RemoteResult:
        label = f"push {branch}" if branch else "push all branches"
        return await self._run(label, lambda env: self._summary(self._repo.push(env, branch)))

    async def pull(self, branch: str) -> list[str]:
        """Fetches, then merges the remote's `branch` into the local one; returns
        the conflicting files, or [] once merged (or already up to date)."""
        result = await self.fetch()
        if not result.ok:
            raise BranchError(result.message)
        status = await asyncio.to_thread(self._repo.remote_ahead_behind, branch)
        if status is None:
            raise BranchError(f"the remote has no branch {branch}")
        if status[1] == 0:
            return []
        async with self._store.lock:
            current = await asyncio.to_thread(self._repo.current_branch)
            conflicts = await asyncio.to_thread(
                self._repo.merge,
                f"origin/{branch}",
                branch,
                f"Merge origin/{branch} into {branch}",
                CurrentAuthor.get(),
            )
            if not conflicts and branch == current:
                for collection in self._collections:
                    await collection.load()
                self._store.last_head = await asyncio.to_thread(self._repo.head)
        return conflicts

    def branch_status(self) -> dict[str, dict[str, int] | None]:
        """Per local branch, how it stands against the remote's as of the last fetch."""
        result: dict[str, dict[str, int] | None] = {}
        for branch in self._repo.branches():
            counts = self._repo.remote_ahead_behind(branch["name"])
            result[branch["name"]] = {"ahead": counts[0], "behind": counts[1]} if counts else None
        return result

    async def _after_commit(self) -> None:
        remote = self.settings()
        if remote is None or not remote.auto_push or not remote.url:
            return
        # Several saves in a row (a merge, a batch) become one push.
        if self._pending is None or self._pending.done():
            self._pending = asyncio.create_task(self._push_soon())

    async def _push_soon(self) -> None:
        await asyncio.sleep(AUTO_PUSH_DELAY)
        result = await self.push(None)
        if not result.ok:
            log.warning("auto-push failed: %s", result.message)

    async def _run(self, action: str, command) -> RemoteResult:  # type: ignore[no-untyped-def]
        remote = self.settings()
        if remote is None or not remote.url:
            raise BranchError("no remote is set up")

        def go() -> str:
            with self._env(remote) as env:
                return command(env)

        try:
            message = await asyncio.to_thread(go)
            result = RemoteResult(
                action=action, ok=True, message=message.strip()[:500], at=self._clock.now()
            )
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            result = RemoteResult(
                action=action, ok=False, message=str(exc)[:500], at=self._clock.now()
            )
        self.last = result
        return result

    @contextmanager
    def _env(self, remote: GitRemote) -> Iterator[dict[str, str]]:
        token = self._box.decrypt(remote.token) if remote.auth == "token" and remote.token else None
        key = None
        if remote.auth == "ssh":
            if not remote.private_key:
                raise RuntimeError("no SSH key yet: generate one first")
            key = self._box.decrypt(remote.private_key)
        with GitCredentials.env(key, token, self._known_hosts) as env:
            yield env

    @staticmethod
    def _summary(porcelain: str) -> str:
        lines = [line for line in porcelain.splitlines() if line[:1] in "*+-! =" and "\t" in line]
        changed = [
            line.split("\t")[1].split(":")[0].removeprefix("refs/heads/")
            for line in lines
            if line[0] != "="
        ]
        return f"pushed {', '.join(changed)}" if changed else "everything was already there"
