from abc import ABC, abstractmethod
from typing import Any

from aios.tools.tool_context import ToolContext


class AiosTool(ABC):
    """A capability ai-os offers its agents. Approval is decided before `run`, by
    the approval policy; a tool only does its job."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """JSON schema of the arguments."""

    @abstractmethod
    async def run(self, args: dict[str, Any], context: ToolContext) -> str: ...
