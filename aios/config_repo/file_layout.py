from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class FileLayout(ABC):
    """How one collection's documents are laid out as files in the repository."""

    @abstractmethod
    def path(self, doc_id: str) -> str:
        """The document's file, relative to the repository root."""

    @abstractmethod
    def ids(self, root: Path) -> list[str]:
        """The ids of the documents present under `root`."""

    @abstractmethod
    def render(self, doc: dict[str, Any]) -> str: ...

    @abstractmethod
    def parse(self, text: str, doc_id: str) -> dict[str, Any]: ...
