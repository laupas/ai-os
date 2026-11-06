from pydantic import BaseModel, Field

from aios.entities.memories.memory_kind import MemoryKind


class MemoryRequest(BaseModel):
    kind: MemoryKind = MemoryKind.NOTE
    subject: str | None = None
    text: str = Field(min_length=1)
    user_id: str | None = None
    """The user it belongs to; None shares it with every user."""
