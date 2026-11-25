import io
import tarfile
from pathlib import Path, PurePosixPath

# Left out, relative to the data dir: what can be lost (logs), what must not travel
# (signed-in browsers, decrypted files, an older ai-os's key file), and the Claude
# CLI's transcripts, sessions and own backups (large, and only for resuming a turn).
LEFT_OUT = (
    "logs",
    "web-sessions",
    "variable-files",
    "secrets.key",
    "claude/projects",
    "claude/sessions",
    "claude/backups",
)
# Never worth keeping, wherever they are: half-written files and macOS litter.
JUNK_PREFIXES = (".tmp-",)
JUNK_NAMES = (".DS_Store",)
# A restore's own working files at the top (`PendingRestore`, `RestoreOnStart`): a
# backup waiting to be applied, and the data a restore replaced.
RESTORE_ENTRIES = (".restore",)
RESTORE_PREFIXES = (".before-restore-",)


class BackupArchive:
    """The data dir as a gzip'd tar, without `LEFT_OUT`. Symbolic links are kept as
    links, never followed, so nothing outside the data dir comes along."""

    def __init__(self, data_dir: Path) -> None:
        self._root = Path(data_dir)

    def build(self) -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            tar.add(self._root, arcname="data", recursive=True, filter=self._keep)
        return buffer.getvalue()

    @staticmethod
    def belongs(inside: PurePosixPath) -> bool:
        """Whether a path, relative to the data dir, is something a backup holds: the
        same rule for making one and for checking one before a restore."""
        if any(inside == PurePosixPath(p) or PurePosixPath(p) in inside.parents for p in LEFT_OUT):
            return False
        top = inside.parts[0] if inside.parts else ""
        if top in RESTORE_ENTRIES or top.startswith(RESTORE_PREFIXES):
            return False
        return not (inside.name in JUNK_NAMES or inside.name.startswith(JUNK_PREFIXES))

    @staticmethod
    def _keep(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
        path = PurePosixPath(info.name)
        inside = path.relative_to("data") if path != PurePosixPath("data") else PurePosixPath()
        if inside.parts and not BackupArchive.belongs(inside):
            return None
        if not (info.isfile() or info.isdir() or info.issym()):
            return None  # no sockets, devices or pipes
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        return info
