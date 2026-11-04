from datetime import UTC, datetime

from pydantic import BaseModel, Field

from aios.entities.memories.memory_kind import MemoryKind


class Memory(BaseModel):
    """Something the user asked ai-os to remember."""

    id: str
    kind: MemoryKind = MemoryKind.NOTE
    subject: str | None = None
    """Who or what it is about, e.g. a person's or project's name."""
    text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
