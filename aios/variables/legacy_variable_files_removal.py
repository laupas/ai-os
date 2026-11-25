import logging
import shutil
from pathlib import Path

from aios.bootstrap.startup_step import StartupStep

log = logging.getLogger(__name__)


class LegacyVariableFilesRemoval(StartupStep):
    """`${file:NAME}` values are decrypted copies, written outside the data dir now
    (`Settings.variable_files_dir`). An older ai-os wrote them into
    `<data>/variable-files`: removed at start, so no copy of the data dir carries them.
    They are written again where they belong when a connector needs them."""

    def __init__(self, legacy_dir: Path, files_dir: Path) -> None:
        self._legacy = Path(legacy_dir)
        self._files = Path(files_dir)

    async def run(self) -> None:
        if not self._legacy.exists() or self._legacy.resolve() == self._files.resolve():
            return
        shutil.rmtree(self._legacy)
        log.info("removed %s: decrypted secrets do not belong in the data dir", self._legacy)
