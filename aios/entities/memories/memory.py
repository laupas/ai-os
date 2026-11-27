from datetime import UTC, datetime

from pydantic import BaseModel, Field

from aios.entities.memories.memory_kind import MemoryKind
from aios.entities.memories.memory_source import MemorySource


class Memory(BaseModel):
    """Something a user asked ai-os to remember."""

    id: str
    user_id: str | None = None
    """The user it belongs to; None makes it shared with every user."""
    kind: MemoryKind = MemoryKind.NOTE
    subject: str | None = None
    """Who or what it is about, e.g. a person's or project's name."""
    text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    """The last change; None for one never changed since it was made."""
    source: MemorySource | None = None
    """Where it was last written; None for memories older than this field."""
