import asyncio
from importlib.metadata import version

from aios.backup.backup_archive import LEFT_OUT, BackupArchive
from aios.backup.backup_cipher import BackupCipher
from aios.backup.backup_header import BackupHeader
from aios.common.clock import Clock


class BackupMaker:
    """A backup of the data dir, ready to download: archived, then sealed with the
    secrets key. Made while ai-os runs: each document is written whole (a temporary
    file, then a rename), so every file in it is complete, though a write during the
    backup may be in it or not."""

    def __init__(self, archive: BackupArchive, cipher: BackupCipher, clock: Clock) -> None:
        self._archive = archive
        self._cipher = cipher
        self._clock = clock

    async def make(self) -> tuple[str, bytes]:
        """The file name and the backup."""
        archive = await asyncio.to_thread(self._archive.build)
        now = self._clock.now()
        header = BackupHeader(
            created_at=now,
            aios_version=version("aios"),
            key_fingerprint=self._cipher.fingerprint(),
            left_out=list(LEFT_OUT),
        )
        sealed = await asyncio.to_thread(self._cipher.seal, header, archive)
        stamp = now.strftime("%Y-%m-%d-%H%M")
        key = self._cipher.fingerprint().replace(" ", "")
        return f"aios-backup-{stamp}-{key}.aiosbackup", sealed
