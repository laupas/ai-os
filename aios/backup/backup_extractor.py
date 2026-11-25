import io
import tarfile
from collections import Counter
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from aios.backup.backup_archive import BackupArchive
from aios.backup.backup_unreadable import BackupUnreadable

ROOT = "data"
# A data dir of ai-os has at least one of these; anything else is not a backup of it.
EXPECTED = ("users", "config")


class BackupExtractor:
    """Checks a backup's archive and unpacks it into the data dir. Every entry has to
    pass Python's `data` filter for that dir (no absolute paths, no `..`, no links
    leading out, no devices) and be something a backup holds at all (`BackupArchive`):
    a file crafted to write anywhere else is refused before anything is touched."""

    def check(self, archive: bytes, data_dir: Path) -> tuple[int, int, dict[str, int]]:
        """Files, unpacked bytes and files per top-level entry; raises
        `BackupUnreadable` for anything a backup of ai-os cannot hold."""
        files = size = 0
        folders: Counter[str] = Counter()
        with self._open(archive) as tar:
            members = list(self._checked(tar, data_dir))
        for member in members:
            if member.isfile():
                files += 1
                size += member.size
                folders[PurePosixPath(member.name).parts[0]] += 1
        if not any(name in folders for name in EXPECTED):
            raise BackupUnreadable("this is not the data dir of ai-os")
        return files, size, dict(sorted(folders.items()))

    def extract(self, archive: bytes, data_dir: Path) -> None:
        with self._open(archive) as tar:
            members = list(self._checked(tar, data_dir))  # all checked before any is written
            tar.extractall(Path(data_dir), members=members, filter="data")

    @staticmethod
    def _checked(tar: tarfile.TarFile, data_dir: Path) -> Iterator[tarfile.TarInfo]:
        """Each entry renamed from `data/<path>` to `<path>`, once it passed."""
        for member in tar.getmembers():
            name = PurePosixPath(member.name)
            if name == PurePosixPath(ROOT):
                continue
            if not name.parts or name.parts[0] != ROOT:
                raise BackupUnreadable(f"an entry outside the data dir: {member.name}")
            inside = member.replace(name=str(name.relative_to(ROOT)), deep=False)
            if not BackupArchive.belongs(PurePosixPath(inside.name)):
                raise BackupUnreadable(f"an entry a backup never holds: {inside.name}")
            try:
                yield tarfile.data_filter(inside, str(data_dir))
            except tarfile.FilterError as exc:
                raise BackupUnreadable(f"an unsafe entry: {member.name} ({exc})") from exc

    @staticmethod
    def _open(archive: bytes) -> tarfile.TarFile:
        try:
            return tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz")
        except (tarfile.TarError, OSError, EOFError) as exc:
            raise BackupUnreadable("the backup's archive is damaged") from exc
