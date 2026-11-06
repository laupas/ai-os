from aios.common.clock import Clock
from aios.config_repo.current_author import CurrentAuthor
from aios.entities.audit.audit_action import AuditAction
from aios.entities.audit.audit_entry import AuditEntry
from aios.storage.append_log import AppendLog

LOG_NAME = "audit"


class AuditTrail:
    """Who changed which setting when, in `<data>/audit.jsonl`.

    The actor is `CurrentAuthor`: the console user while their request is handled,
    ai-os itself otherwise (an agent's approved write, a startup migration).
    """

    def __init__(self, log: AppendLog, clock: Clock) -> None:
        self._log = log
        self._clock = clock

    async def record(
        self,
        area: str,
        item: str,
        action: AuditAction,
        fields: list[str] | None = None,
        detail: str | None = None,
    ) -> None:
        author = CurrentAuthor.get()
        entry = AuditEntry(
            at=self._clock.now(),
            actor=author.name,
            actor_email=author.email,
            area=area,
            item=item,
            action=action,
            fields=fields or [],
            detail=detail,
        )
        await self._log.append(LOG_NAME, entry.model_dump(mode="json"))

    async def entries(self) -> list[AuditEntry]:
        """Newest first."""
        records = await self._log.read_all(LOG_NAME)
        return [AuditEntry.model_validate(r) for r in reversed(records)]
