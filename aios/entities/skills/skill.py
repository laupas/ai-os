from pydantic import BaseModel


class Skill(BaseModel):
    """Instructions an agent loads when a task calls for them. `id` is its name.

    Stored in /data and edited in the console; the repo's `skills/` only seed an
    empty store.
    """

    id: str
    description: str
    """When to use it: the agent reads this to decide whether to load the skill."""
    content: str
    """The instructions, as Markdown (SKILL.md without its front matter)."""

    @property
    def name(self) -> str:
        return self.id
