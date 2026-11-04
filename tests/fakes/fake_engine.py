from collections.abc import Awaitable, Callable

from aios.engine.agent_engine import AgentEngine, ProgressCallback, TextCallback
from aios.engine.text_delta import TextDelta
from aios.engine.turn_request import TurnRequest
from aios.engine.turn_result import TurnResult
from aios.progress.progress_event import ProgressEvent


class FakeEngine(AgentEngine):
    """Answers with a fixed reply, or runs a scripted behaviour."""

    def __init__(
        self,
        reply: str = "ok",
        session_id: str = "session-1",
        behaviour: Callable[[TurnRequest], Awaitable[None]] | None = None,
        deltas: list[TextDelta] | None = None,
        progress: list[ProgressEvent] | None = None,
    ) -> None:
        self._reply = reply
        self._session_id = session_id
        self._behaviour = behaviour
        self._deltas = deltas or []
        self._progress = progress or []
        self.requests: list[TurnRequest] = []

    async def run_turn(
        self,
        request: TurnRequest,
        on_progress: ProgressCallback,
        on_text: TextCallback | None = None,
    ) -> TurnResult:
        self.requests.append(request)
        if self._behaviour is not None:
            await self._behaviour(request)
        for event in self._progress:
            await on_progress(event)
        for delta in self._deltas:
            if on_text is not None:
                await on_text(delta)
        return TurnResult(text=self._reply, session_id=self._session_id)
