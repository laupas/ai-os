from dependency_injector import containers, providers

from aios.backup.backup_archive import BackupArchive
from aios.backup.backup_cipher import BackupCipher
from aios.backup.backup_extractor import BackupExtractor
from aios.backup.backup_maker import BackupMaker
from aios.backup.pending_restore import PendingRestore
from aios.backup.restore_audit import RestoreAudit


class BackupContainer(containers.DeclarativeContainer):
    """Backups of the data dir, sealed with the secrets key, and restoring one. The
    restore itself runs before this container exists (`RestoreOnStart`, `__main__`)."""

    settings = providers.Dependency()
    box = providers.Dependency()
    clock = providers.Dependency()
    audit_trail = providers.Dependency()

    cipher = providers.Singleton(BackupCipher, box=box)
    extractor = providers.Singleton(BackupExtractor)
    pending = providers.Singleton(PendingRestore, data_dir=settings.provided.data_dir)
    maker = providers.Singleton(
        BackupMaker,
        archive=providers.Singleton(BackupArchive, data_dir=settings.provided.data_dir),
        cipher=cipher,
        clock=clock,
    )
    restore_audit = providers.Singleton(RestoreAudit, pending=pending, trail=audit_trail)
