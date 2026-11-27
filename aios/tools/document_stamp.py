from abc import ABC, abstractmethod

from pydantic import BaseModel

from aios.tools.tool_context import ToolContext


class DocumentStamp(ABC):
    """Fields ai-os sets itself when an agent writes a document of one collection,
    whatever the agent sent for them."""

    @property
    @abstractmethod
    def collection(self) -> str: ...

    @abstractmethod
    def stamp(self, item: BaseModel, existing: BaseModel | None, context: ToolContext) -> BaseModel:
        """The item to store; `existing` is the document it replaces, if any."""
