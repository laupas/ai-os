import os
from pathlib import Path

from aios.backup.backup_contents import BackupContents
from aios.backup.restore_record import RestoreRecord

FOLDER = ".restore"


class PendingRestore:
    """A backup waiting to be restored, in `<data>/.restore`: uploaded and checked
    (`stage`), then confirmed by an administrator, then applied at the next start
    (`RestoreOnStart`). Still sealed while it waits. Also keeps what happened: the
    reason a restore failed, and the last one that ran."""

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir) / FOLDER

    def stage(self, blob: bytes, contents: BackupContents) -> None:
        self.discard()
        self._dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._write("pending.aiosbackup", blob)
        self._write("pending.json", contents.model_dump_json().encode())

    def pending(self) -> BackupContents | None:
        path = self._dir / "pending.json"
        return BackupContents.model_validate_json(path.read_bytes()) if path.exists() else None

    def blob(self) -> bytes:
        return (self._dir / "pending.aiosbackup").read_bytes()

    def confirm(self) -> None:
        if self.pending() is None:
            raise FileNotFoundError("no backup is waiting to be restored")
        self._write("confirmed", b"")

    def confirmed(self) -> bool:
        return (self._dir / "confirmed").exists() and self.pending() is not None

    def discard(self) -> None:
        for name in ("pending.aiosbackup", "pending.json", "confirmed", "failed.txt"):
            (self._dir / name).unlink(missing_ok=True)

    def fail(self, reason: str) -> None:
        """Keeps the backup, so it can be looked at or discarded, but not run again."""
        (self._dir / "confirmed").unlink(missing_ok=True)
        self._write("failed.txt", reason.encode())

    def failure(self) -> str | None:
        path = self._dir / "failed.txt"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def finish(self, record: RestoreRecord) -> None:
        for name in ("pending.aiosbackup", "pending.json", "confirmed", "failed.txt"):
            (self._dir / name).unlink(missing_ok=True)
        self.keep(record)

    def last(self) -> RestoreRecord | None:
        path = self._dir / "last.json"
        return RestoreRecord.model_validate_json(path.read_bytes()) if path.exists() else None

    def keep(self, record: RestoreRecord) -> None:
        self._dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._write("last.json", record.model_dump_json().encode())

    def _write(self, name: str, data: bytes) -> None:
        path = self._dir / name
        tmp = path.with_name(f".tmp-{name}")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
