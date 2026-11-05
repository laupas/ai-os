import asyncio
import logging

from claude_agent_sdk import ClaudeSDKClient, ResultMessage, SystemMessage

from aios.connectors.connector_status_board import ConnectorStatusBoard
from aios.engine.agent_engine import AgentEngine, ProgressCallback, TextCallback
from aios.engine.claude_options_factory import ClaudeOptionsFactory
from aios.engine.progress_stream_mapper import ProgressStreamMapper
from aios.engine.text_stream_mapper import TextStreamMapper
from aios.engine.turn_deadline import TurnDeadline
from aios.engine.turn_request import TurnRequest
from aios.engine.turn_result import TurnResult

log = logging.getLogger(__name__)


class ClaudeAgentEngine(AgentEngine):
    """Runs a turn with a fresh SDK client that resumes the conversation's session.

    A client per turn is slower to start than a warm one, but context can never
    be lost: it lives in the stored session id, not in a running process.
    """

    def __init__(
        self,
        options_factory: ClaudeOptionsFactory,
        mapper: ProgressStreamMapper,
        text_mapper: TextStreamMapper,
        timeout_seconds: float,
        board: ConnectorStatusBoard | None = None,
    ) -> None:
        self._options = options_factory
        self._mapper = mapper
        self._text_mapper = text_mapper
        self._timeout = timeout_seconds
        self._board = board

    async def run_turn(
        self,
        request: TurnRequest,
        on_progress: ProgressCallback,
        on_text: TextCallback | None = None,
    ) -> TurnResult:
        resume = request.conversation.agent_session_id
        acted = False

        async def tracking_progress(event):  # type: ignore[no-untyped-def]
            nonlocal acted
            acted = True
            await on_progress(event)

        try:
            return await self._attempt(request, resume, tracking_progress, on_text)
        except (TimeoutError, asyncio.CancelledError):
            raise
        except Exception as exc:
            # A session that cannot be resumed (e.g. its transcript is gone) fails at
            # once. Retrying without it is only safe when nothing was done yet.
            if resume is None or acted:
                raise
            log.warning("could not resume session %s (%s); starting a new one", resume, exc)
            return await self._attempt(request, None, on_progress, on_text)

    async def _attempt(
        self,
        request: TurnRequest,
        resume: str | None,
        on_progress: ProgressCallback,
        on_text: TextCallback | None,
    ) -> TurnResult:
        deadline = TurnDeadline(self._timeout)
        options = self._options.create(request, resume, deadline)
        result: ResultMessage | None = None
        try:
            async with deadline.running(), ClaudeSDKClient(options=options) as client:
                await client.query(request.text)
                async for message in client.receive_response():
                    if (
                        self._board
                        and isinstance(message, SystemMessage)
                        and message.subtype == "init"
                    ):
                        self._board.record(message.data)
                    for event in self._mapper.events(message):
                        await on_progress(event)
                    if on_text is not None and (delta := self._text_mapper.delta(message)):
                        await on_text(delta)
                    if isinstance(message, ResultMessage):
                        result = message
        except TimeoutError as exc:
            minutes = round(self._timeout / 60)
            raise TimeoutError(
                f"the agent worked for more than {minutes} minutes and was stopped"
            ) from exc
        if result is None:
            raise RuntimeError("the agent ended without a result")
        if result.is_error:
            raise RuntimeError(result.result or result.subtype)
        return TurnResult(text=result.result or "", session_id=result.session_id)
