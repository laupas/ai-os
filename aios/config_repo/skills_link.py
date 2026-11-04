import asyncio
import logging
from pathlib import Path

from aios.bootstrap.startup_step import StartupStep

log = logging.getLogger(__name__)


class SkillsLink(StartupStep):
    """Points `.claude/skills`, the only place the CLI reads skills from, at the
    configuration repository's `skills/`, whose files are already in the CLI's
    format. The image ships the link; this makes it when running from a checkout.
    A real directory there is left alone.
    """

    def __init__(self, link: Path, target: Path) -> None:
        self._link = Path(link)
        self._target = Path(target)

    async def run(self) -> None:
        await asyncio.to_thread(self._ensure)

    def _ensure(self) -> None:
        self._target.mkdir(parents=True, exist_ok=True)
        if self._link.is_symlink():
            if self._link.resolve() == self._target.resolve():
                return
            self._link.unlink()
        elif self._link.exists():
            log.warning("%s is a directory, not a link: skills are read from it", self._link)
            return
        self._link.parent.mkdir(parents=True, exist_ok=True)
        self._link.symlink_to(self._target)
        log.info("linked %s to %s", self._link, self._target)
