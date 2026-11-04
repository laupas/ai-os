from pydantic import BaseModel, Field


class SkillRequest(BaseModel):
    """A skill as the console sends it. `name` is read only when creating one."""

    name: str | None = None
    description: str = Field(min_length=1)
    content: str = Field(min_length=1)
