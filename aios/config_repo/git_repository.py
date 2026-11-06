import logging
import os
import subprocess
import tempfile
from pathlib import Path

from aios.config_repo.change_author import ChangeAuthor

log = logging.getLogger(__name__)


class GitRepository:
    """The git commands the configuration repository needs, through the git CLI.

    Blocking: callers run these in a thread.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def exists(self) -> bool:
        return (self._root / ".git").is_dir()

    def clone(self, url: str, env: dict[str, str]) -> None:
        self._root.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--quiet", url, str(self._root)],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, **env},
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr.strip()}")

    def init(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        self._git("init", "--quiet", "--initial-branch=main")

    def head(self) -> str | None:
        result = self._git("rev-parse", "--verify", "--quiet", "HEAD", check=False)
        return result.stdout.strip() or None

    def commit(self, paths: list[str], message: str, author: ChangeAuthor) -> str | None:
        """Commits exactly `paths` (added, changed or removed); None when nothing in
        them changed. Other edits in the working tree are left alone."""
        self._git("add", "--all", "--", *paths)
        staged = self._git("diff", "--cached", "--quiet", "--", *paths, check=False)
        if staged.returncode == 0:
            return None
        identity = f"{author.name} <{author.email}>"
        self._git(
            "-c", f"user.name={author.name}", "-c", f"user.email={author.email}",
            "commit", "--quiet", f"--author={identity}", "-m", message, "--", *paths,
        )  # fmt: skip
        return self.head()

    def log(self, path: str, limit: int = 50) -> list[dict[str, str]]:
        """Newest first: commit, author, date (ISO) and subject."""
        result = self._git(
            "log", f"-{limit}", "--follow", "--format=%H%x1f%an%x1f%ae%x1f%aI%x1f%s",
            "--", path, check=False,
        )  # fmt: skip
        entries = []
        for line in result.stdout.splitlines():
            commit, name, email, date, subject = line.split("\x1f")
            entries.append(
                {"commit": commit, "author": name, "email": email, "date": date, "subject": subject}
            )
        return entries

    def changes(
        self, limit: int, ref: str = "HEAD", path: str | None = None, skip: int = 0
    ) -> list[dict]:
        """The newest `limit` commits of `ref` (after skipping `skip`), newest first,
        each with the files it touched: commit, author, email, date, subject and
        `files`, a list of (status letter, path). With `path`, only the commits
        touching it."""
        result = self._git(
            "log", f"-{limit}", f"--skip={skip}", "--name-status", "--no-renames",
            "--format=%x1e%H%x1f%an%x1f%ae%x1f%aI%x1f%s", ref, "--", *([path] if path else []),
            check=False,
        )  # fmt: skip
        entries = []
        for block in result.stdout.split("\x1e")[1:]:
            head, *lines = block.splitlines()
            commit, name, email, date, subject = head.split("\x1f")
            files = []
            for line in lines:
                status, _, file = line.partition("\t")
                if file:
                    files.append((status[:1], file))
            entries.append(
                {"commit": commit, "author": name, "email": email, "date": date,
                 "subject": subject, "files": files}
            )  # fmt: skip
        return entries

    def resolve(self, ref: str) -> str | None:
        """The commit `ref` names (a branch or a commit id), or None."""
        if not ref or ref.startswith("-"):
            return None
        result = self._git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
        return result.stdout.strip() or None

    def tree(self, ref: str) -> list[dict]:
        """Every file in `ref`: path, blob id and size in bytes."""
        result = self._git("ls-tree", "-r", "--long", "-z", ref)
        files = []
        for entry in result.stdout.split("\0"):
            if not entry:
                continue
            meta, _, path = entry.partition("\t")
            _mode, kind, blob, size = meta.split()
            if kind == "blob":
                files.append({"path": path, "blob": blob, "size": int(size)})
        return files

    def blob(self, ref: str, path: str) -> str | None:
        """The blob id of `path` in `ref`; None when it is not there."""
        result = self._git("rev-parse", "--verify", "--quiet", f"{ref}:{path}", check=False)
        return result.stdout.strip() or None

    def commit_on(
        self, branch: str, files: dict[str, str | None], message: str, author: ChangeAuthor
    ) -> str | None:
        """Commits `files` (text, or None to remove) on `branch` in a temporary
        worktree, so the checked-out configuration is not touched. Returns the new
        commit, or None when nothing changed."""
        with tempfile.TemporaryDirectory(prefix="aios-edit-") as tmp:
            place = Path(tmp) / "tree"
            self._git("worktree", "add", "--quiet", str(place), branch)
            try:
                other = GitRepository(place)
                for path, text in files.items():
                    file = place / path
                    if text is None:
                        file.unlink(missing_ok=True)
                    else:
                        file.parent.mkdir(parents=True, exist_ok=True)
                        file.write_text(text, encoding="utf-8")
                return other.commit(list(files), message, author)
            finally:
                self._git("worktree", "remove", "--force", str(place), check=False)
                self._git("worktree", "prune", check=False)

    def show(self, commit: str, path: str) -> str | None:
        """The file as it was in `commit`; None when it did not exist there."""
        result = self._git("show", f"{commit}:{path}", check=False)
        return result.stdout if result.returncode == 0 else None

    def diff(self, commit: str, path: str) -> str:
        """What `commit` changed in `path`."""
        result = self._git("show", "--format=", commit, "--", path, check=False)
        return result.stdout

    def current_branch(self) -> str:
        return self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    def branches(self) -> list[dict[str, str]]:
        """Every branch with its newest commit, newest branch first."""
        result = self._git(
            "for-each-ref", "--sort=-committerdate",
            "--format=%(refname:short)%1f%(objectname)%1f%(authorname)%1f%(committerdate:iso-strict)%1f%(subject)",
            "refs/heads",
        )  # fmt: skip
        rows = []
        for line in result.stdout.splitlines():
            name, commit, author, date, subject = line.split("\x1f")
            rows.append(
                {"name": name, "commit": commit, "author": author, "date": date, "subject": subject}
            )
        return rows

    def ahead_behind(self, branch: str, base: str) -> tuple[int, int]:
        """Commits on `branch` that `base` lacks, and the other way round."""
        counts = self._git("rev-list", "--left-right", "--count", f"{branch}...{base}").stdout
        ahead, behind = counts.split()
        return int(ahead), int(behind)

    def is_clean(self) -> bool:
        return not self._git("status", "--porcelain").stdout.strip()

    def create_branch(self, name: str, start: str) -> None:
        self._git("branch", name, start)

    def checkout(self, name: str) -> None:
        self._git("checkout", "--quiet", name)

    def delete_branch(self, name: str, force: bool = False) -> None:
        self._git("branch", "-D" if force else "-d", name)

    def changed_files(self, branch: str, base: str) -> list[dict[str, str]]:
        """What `branch` changed since it left `base`: status letter and path."""
        result = self._git("diff", "--name-status", f"{base}...{branch}")
        rows = []
        for line in result.stdout.splitlines():
            status, _, path = line.partition("\t")
            rows.append({"status": status[:1], "path": path.split("\t")[-1]})
        return rows

    def merge(self, source: str, target: str, message: str, author: ChangeAuthor) -> list[str]:
        """Merges `source` into `target`; returns the conflicting files, or [] once
        merged. A conflict is aborted, never left half-done. A target that is not
        checked out is merged in a temporary worktree, so the running configuration
        is not touched."""
        if target == self.current_branch():
            return self._merge_in(self._root, source, message, author)
        with tempfile.TemporaryDirectory(prefix="aios-merge-") as tmp:
            place = Path(tmp) / "tree"
            self._git("worktree", "add", "--quiet", str(place), target)
            try:
                return self._merge_in(place, source, message, author)
            finally:
                self._git("worktree", "remove", "--force", str(place), check=False)
                self._git("worktree", "prune", check=False)

    def _merge_in(self, tree: Path, source: str, message: str, author: ChangeAuthor) -> list[str]:
        identity = ["-c", f"user.name={author.name}", "-c", f"user.email={author.email}"]
        result = subprocess.run(
            [
                "git",
                "-C",
                str(tree),
                *identity,
                "merge",
                "--no-ff",
                "--quiet",
                "-m",
                message,
                source,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return []
        conflicts = subprocess.run(
            ["git", "-C", str(tree), "diff", "--name-only", "--diff-filter=U"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.split()
        subprocess.run(
            ["git", "-C", str(tree), "merge", "--abort"], capture_output=True, check=False
        )
        if not conflicts:
            raise RuntimeError(
                f"git merge failed: {result.stderr.strip() or result.stdout.strip()}"
            )
        return conflicts

    def remote_url(self, name: str = "origin") -> str | None:
        result = self._git("remote", "get-url", name, check=False)
        return result.stdout.strip() or None

    def set_remote(self, url: str, name: str = "origin") -> None:
        if self.remote_url(name) is None:
            self._git("remote", "add", name, url)
        else:
            self._git("remote", "set-url", name, url)

    def remove_remote(self, name: str = "origin") -> None:
        self._git("remote", "remove", name, check=False)

    def ls_remote(self, env: dict[str, str], name: str = "origin") -> str:
        """Raises with git's message when the remote cannot be reached or read."""
        return self._git("ls-remote", "--heads", name, env=env, timeout=60).stdout

    def fetch(self, env: dict[str, str], name: str = "origin") -> None:
        self._git("fetch", "--prune", name, env=env, timeout=120)

    def push(self, env: dict[str, str], branch: str | None, name: str = "origin") -> str:
        """Pushes one branch, or every branch when `branch` is None."""
        refs = (
            [f"refs/heads/{branch}:refs/heads/{branch}"]
            if branch
            else ["refs/heads/*:refs/heads/*"]
        )
        result = self._git("push", "--porcelain", name, *refs, env=env, timeout=120)
        return result.stdout

    def remote_ahead_behind(self, branch: str, name: str = "origin") -> tuple[int, int] | None:
        """Commits the local branch has that the remote's lacks, and the other way
        round, as of the last fetch; None when the remote has no such branch."""
        ref = f"refs/remotes/{name}/{branch}"
        if self._git("rev-parse", "--verify", "--quiet", ref, check=False).returncode != 0:
            return None
        return self.ahead_behind(branch, ref)

    def _git(
        self,
        *args: str,
        check: bool = True,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", "-C", str(self._root), *args],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, **env} if env else None,
            timeout=timeout,
        )
        if check and result.returncode != 0:
            raise RuntimeError(f"git {args[0]} failed: {result.stderr.strip()}")
        return result
