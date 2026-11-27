import re

from aios.entities.memories.memory import Memory
from aios.entities.memories.memory_kind import MemoryKind
from aios.entities.users.user import User
from aios.storage.collection import Collection


class MemoryPromptSection:
    """What a user's turn is told of their memories and the shared ones: every
    preference in full, the names of the people and projects something is saved
    about, and in full what is saved about those the message names. Notes are left
    to be looked up."""

    MAX_SUBJECTS = 40
    MAX_MENTIONED = 5
    MAX_TEXT = 500

    _INDEXED = (MemoryKind.PERSON, MemoryKind.PROJECT)
    _HEADINGS = {MemoryKind.PERSON: "People", MemoryKind.PROJECT: "Projects"}

    def __init__(self, memories: Collection[Memory]) -> None:
        self._memories = memories

    def lines(self, user: User, message: str = "") -> list[str]:
        visible = [m for m in self._memories.all() if m.user_id in (None, user.id)]
        lines = self._preferences(visible, user)
        indexed = sorted(
            (m for m in visible if m.kind in self._INDEXED and m.subject),
            key=lambda m: m.updated_at or m.created_at,
            reverse=True,
        )
        if indexed:
            lines += self._index(indexed)
        mentioned = [m for m in indexed if self._names(message, m.subject or "")]
        if mentioned:
            lines += [
                "",
                "# Saved about who or what this message names",
            ] + [self._line(m) for m in mentioned[: self.MAX_MENTIONED]]
        return lines

    def _preferences(self, visible: list[Memory], user: User) -> list[str]:
        preferences = [m for m in visible if m.kind is MemoryKind.PREFERENCE]
        shared = [m for m in preferences if m.user_id is None]
        own = [m for m in preferences if m.user_id == user.id]
        if not preferences:
            return []
        lines = [
            "",
            "# Remembered preferences",
            "Apply each one only where it fits: a mail signoff belongs in mails, never "
            "in your chat replies.",
        ]
        if shared:
            lines += ["", "## Shared by every user"] + [self._line(m) for m in shared]
        if own:
            lines += ["", f"## {user.name}'s own"] + [self._line(m) for m in own]
        return lines

    def _index(self, indexed: list[Memory]) -> list[str]:
        lines = [
            "",
            "# Saved people and projects",
            "Something is saved about each of these; look it up (`data_query` on "
            "`memories`, or the memory agent) when it matters.",
        ]
        for kind in self._INDEXED:
            subjects = list(dict.fromkeys(m.subject for m in indexed if m.kind is kind))
            if subjects:
                lines.append(
                    f"- {self._HEADINGS[kind]}: {', '.join(subjects[: self.MAX_SUBJECTS])}"  # type: ignore[arg-type]
                )
        return lines

    @staticmethod
    def _names(message: str, subject: str) -> bool:
        return bool(message) and re.search(rf"\b{re.escape(subject)}\b", message, re.I) is not None

    @classmethod
    def _line(cls, memory: Memory) -> str:
        text = " ".join(memory.text.split())
        if len(text) > cls.MAX_TEXT:
            text = text[: cls.MAX_TEXT] + "…"
        return f"- {memory.subject + ': ' if memory.subject else ''}{text}"
