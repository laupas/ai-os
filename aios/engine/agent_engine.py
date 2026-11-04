from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from aios.engine.text_delta import TextDelta
from aios.engine.turn_request import TurnRequest
from aios.engine.turn_result import TurnResult
from aios.progress.progress_event import ProgressEvent

ProgressCallback = Callable[[ProgressEvent], Awaitable[None]]
TextCallback = Callable[[TextDelta], Awaitable[None]]


class AgentEngine(ABC):
    """Runs one turn of a conversation and returns the reply. `on_text`, when given,
    receives the reply while it is being written; the returned text is what counts."""

    @abstractmethod
    async def run_turn(
        self,
        request: TurnRequest,
        on_progress: ProgressCallback,
        on_text: TextCallback | None = None,
    ) -> TurnResult: ...
