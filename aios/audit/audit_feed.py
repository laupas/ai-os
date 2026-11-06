from aios.audit.audit_trail import AuditTrail
from aios.audit.config_history import ConfigHistory
from aios.entities.audit.audit_entry import AuditEntry


class AuditFeed:
    """Every settings change in one list, newest first: the audit trail for what
    lives in the data dir, the git history for what lives in the configuration
    repository."""

    def __init__(self, trail: AuditTrail, history: ConfigHistory | None = None) -> None:
        self._trail = trail
        self._history = history

    async def diff(self, commit: str) -> str | None:
        """What a commit in the configuration history changed; None without one."""
        return None if self._history is None else await self._history.diff(commit)

    async def entries(self, limit: int, area: str | None = None) -> list[AuditEntry]:
        entries = await self._trail.entries()
        if self._history is not None:
            entries += await self._history.entries(limit)
        entries = [e for e in entries if not area or e.area == area]
        entries.sort(key=lambda e: e.at, reverse=True)
        return entries[:limit]
