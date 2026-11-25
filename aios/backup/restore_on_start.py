import logging
import shutil
from pathlib import Path

from aios.backup.backup_cipher import BackupCipher
from aios.backup.backup_extractor import BackupExtractor
from aios.backup.backup_unreadable import BackupUnreadable
from aios.backup.pending_restore import FOLDER, PendingRestore
from aios.backup.restore_record import RestoreRecord
from aios.common.clock import Clock

log = logging.getLogger(__name__)

# What a restore leaves where it is: what a backup does not hold and must not lose
# (the logs, the Claude CLI's transcripts, an older ai-os's key file), and its own files.
KEPT = ("logs", "secrets.key", FOLDER)
KEPT_IN_CLAUDE = ("projects", "sessions", "backups")
ASIDE = ".before-restore-"


class RestoreOnStart:
    """Applies a confirmed restore at start, before anything reads the data dir: the
    data in place moves into `<data>/.before-restore-<time>/`, the backup is unpacked
    in its stead. If unpacking fails, what was unpacked is removed and the data moves
    back; the start then goes on with it. Run from `__main__`, ahead of everything.

    Secrets in a backup made with a previous key are moved onto the key in use by
    `SecretsKeyRotation`, a little later in the same start."""

    def __init__(
        self,
        data_dir: Path,
        pending: PendingRestore,
        cipher: BackupCipher,
        extractor: BackupExtractor,
        clock: Clock,
    ) -> None:
        self._data = Path(data_dir)
        self._pending = pending
        self._cipher = cipher
        self._extractor = extractor
        self._clock = clock

    def run(self) -> None:
        if not self._pending.confirmed():
            return
        contents = self._pending.pending()
        assert contents is not None
        try:
            archive = self._cipher.open(self._pending.blob())
            self._extractor.check(archive, self._data)
        except (BackupUnreadable, OSError) as exc:
            log.error("the backup cannot be restored, nothing changed: %s", exc)
            self._pending.fail(str(exc))
            return
        now = self._clock.now()
        aside = self._data / f"{ASIDE}{now.strftime('%Y-%m-%d-%H%M%S')}"
        moved = self._move_aside(aside)
        try:
            self._extractor.extract(archive, self._data)
        except Exception as exc:
            log.exception("restoring failed; putting the data back")
            self._clear_restored()
            self._move_back(aside, moved)
            self._pending.fail(f"unpacking failed, the data was put back: {exc}")
            return
        self._pending.finish(RestoreRecord(restored_at=now, backup=contents, kept_in=aside.name))
        log.warning(
            "restored the backup of %s (key %s); the data it replaced is in %s",
            contents.created_at.isoformat(),
            contents.key_fingerprint,
            aside,
        )

    def _movable(self) -> list[Path]:
        """Entries of the data dir to move aside, relative to it."""
        entries: list[Path] = []
        for entry in sorted(self._data.iterdir()):
            if entry.name in KEPT or entry.name.startswith(ASIDE):
                continue
            if entry.name == "claude" and entry.is_dir():
                entries += [
                    Path("claude") / child.name
                    for child in sorted(entry.iterdir())
                    if child.name not in KEPT_IN_CLAUDE
                ]
                continue
            entries.append(Path(entry.name))
        return entries

    def _move_aside(self, aside: Path) -> list[Path]:
        moved = self._movable()
        for relative in moved:
            target = aside / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(self._data / relative, target)
        return moved

    def _clear_restored(self) -> None:
        for relative in self._movable():
            path = self._data / relative
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)

    def _move_back(self, aside: Path, moved: list[Path]) -> None:
        for relative in moved:
            (self._data / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(aside / relative, self._data / relative)
        shutil.rmtree(aside, ignore_errors=True)
