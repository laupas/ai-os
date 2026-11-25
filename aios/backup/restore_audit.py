from aios.audit.audit_trail import AuditTrail
from aios.backup.pending_restore import PendingRestore
from aios.bootstrap.startup_step import StartupStep
from aios.entities.audit.audit_action import AuditAction


class RestoreAudit(StartupStep):
    """A restore runs before the audit trail exists (`RestoreOnStart`): recorded at the
    first start after it, in the trail the backup brought along."""

    def __init__(self, pending: PendingRestore, trail: AuditTrail) -> None:
        self._pending = pending
        self._trail = trail

    async def run(self) -> None:
        record = self._pending.last()
        if record is None or record.recorded:
            return
        await self._trail.record(
            "backup",
            "restore",
            AuditAction.PERFORMED,
            detail=(
                f"from the backup of {record.backup.created_at:%Y-%m-%d %H:%M} "
                f"(key {record.backup.key_fingerprint}); "
                f"the data it replaced is in {record.kept_in}"
            ),
        )
        self._pending.keep(record.model_copy(update={"recorded": True}))
