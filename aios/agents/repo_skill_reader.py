import logging
from pathlib import Path

import yaml

from aios.entities.skills.skill import Skill

log = logging.getLogger(__name__)


class RepoSkillReader:
    """Reads the skills that ship with ai-os from `skills/<name>/SKILL.md`, to seed
    the store."""

    def __init__(self, skills_dir: Path) -> None:
        self._dir = Path(skills_dir)

    def read(self) -> list[Skill]:
        return [self._parse(path) for path in sorted(self._dir.glob("*/SKILL.md"))]

    @staticmethod
    def _parse(path: Path) -> Skill:
        text = path.read_text(encoding="utf-8")
        meta: dict = {}
        body = text
        if text.startswith("---\n"):
            head, _, body = text[4:].partition("\n---\n")
            try:
                meta = yaml.safe_load(head) or {}
            except yaml.YAMLError as exc:
                log.error("bad front matter in %s: %s", path, exc)
        return Skill(
            id=path.parent.name,
            description=str(meta.get("description") or ""),
            content=body.strip() + "\n",
        )
