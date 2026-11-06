import asyncio
from datetime import datetime
from pathlib import PurePosixPath

from aios.config_repo.git_repository import GitRepository
from aios.entities.audit.audit_action import AuditAction
from aios.entities.audit.audit_entry import AuditEntry

STATUS = {"A": AuditAction.CREATED, "D": AuditAction.DELETED}


class ConfigHistory:
    """The configuration repository's commits as audit entries, one per file a
    commit touched. Includes commits made on the host, which nothing else sees.

    Reads the checked-out branch: after a switch, the history is that branch's.
    """

    def __init__(self, repo: GitRepository) -> None:
        self._repo = repo

    async def entries(self, limit: int) -> list[AuditEntry]:
        """Newest first."""
        if not self._repo.exists():
            return []
        commits = await asyncio.to_thread(self._repo.changes, limit)
        return [self._entry(c, status, path) for c in commits for status, path in c["files"]]

    async def diff(self, commit: str) -> str:
        """Everything `commit` changed."""
        return await asyncio.to_thread(self._repo.diff, commit, ".")

    @staticmethod
    def _entry(commit: dict, status: str, path: str) -> AuditEntry:
        area, item = ConfigHistory.place(path)
        return AuditEntry(
            at=datetime.fromisoformat(commit["date"]),
            actor=commit["author"],
            actor_email=commit["email"],
            area=area,
            item=item,
            action=STATUS.get(status, AuditAction.CHANGED),
            detail=commit["subject"],
            commit=commit["commit"],
        )

    @staticmethod
    def place(path: str) -> tuple[str, str]:
        """`agents/mail.md` -> (agents, mail), `skills/x/SKILL.md` -> (skills, x),
        `aios.yaml` -> (aios.yaml, aios.yaml)."""
        parts = PurePosixPath(path).parts
        if len(parts) == 1:
            return path, path
        return parts[0], PurePosixPath(parts[1]).stem
