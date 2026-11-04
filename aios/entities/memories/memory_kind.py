from enum import StrEnum


class MemoryKind(StrEnum):
    PREFERENCE = "preference"
    """Stable facts about the user (location, tone, signoff). Shown to every agent."""

    PERSON = "person"
    PROJECT = "project"
    NOTE = "note"
    """Anything else the user asked to remember, like a journal entry."""
