import re

from aios.agents.catalog_error import CatalogError
from aios.entities.skills.skill import Skill
from aios.storage.collection import Collection

NAME = re.compile(r"^[a-z][a-z0-9-]{0,40}$")


class SkillCatalog:
    """Every skill. They are files in the configuration repository's `skills/`,
    which `.claude/skills` links to for the CLI; which agent may use which skill is
    part of the agent."""

    def __init__(self, skills: Collection[Skill]) -> None:
        self._skills = skills

    def all(self) -> list[Skill]:
        return sorted(self._skills.all(), key=lambda s: s.id)

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def names(self) -> set[str]:
        return {s.id for s in self._skills.all()}

    async def save(self, skill: Skill) -> Skill:
        if not NAME.match(skill.id):
            raise CatalogError("a name is lower-case letters, digits and dashes")
        if not skill.description.strip() or not skill.content.strip():
            raise CatalogError("a skill needs a description and instructions")
        return await self._skills.put(skill)

    async def delete(self, name: str) -> None:
        await self._skills.delete(name)
