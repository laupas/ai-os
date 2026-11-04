import asyncio
import logging
import sys
import time
from collections.abc import Callable

from aios.approvals.approval_answer_handler import ApprovalAnswerHandler
from aios.channels.message_channel import MessageChannel
from aios.channels.thread_starter import ThreadStarter
from aios.conversations.inbound_handler import InboundHandler
from aios.conversations.inbound_message import InboundMessage
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.channel_account import ChannelAccount
from aios.progress.progress_event import ProgressEvent
from aios.progress.progress_reporter import ProgressReporter

log = logging.getLogger(__name__)

HELP = "Commands: /new (new conversation), /stop (stop the running turn), /quit"


class CliChannel(MessageChannel, ProgressReporter, ThreadStarter):
    """Talk to ai-os in the terminal. The sender is always the local account, which
    only the owner has. Conversation numbers restart at 1, so after a restart the
    first conversation continues where it left off.
    """

    ACCOUNT = ChannelAccount(channel="cli", address="local")

    def __init__(
        self,
        read_line: Callable[[], str] = sys.stdin.readline,
        write: Callable[[str], None] | None = None,
        interactive: bool = True,
    ) -> None:
        self._read_line = read_line
        self._interactive = interactive
        self._write = write or self._print
        self._thread = 1
        self._tasks: set[asyncio.Task[None]] = set()
        self._started = 0

    @property
    def name(self) -> str:
        return "cli"

    async def start(self, inbound: InboundHandler, answers: ApprovalAnswerHandler) -> None:
        if not self._interactive:
            # In a container stdin is empty, and its end would read as /quit and stop
            # ai-os altogether. Without a terminal the channel simply waits.
            log.warning("cli channel enabled but there is no terminal; it stays idle")
            await asyncio.Event().wait()
        self._write(f"ai-os ready. {HELP}")
        while True:
            line = await asyncio.to_thread(self._read_line)
            if line == "":
                break  # end of input: let running turns finish
            text = line.strip()
            if not text:
                continue
            if text == "/quit":
                for task in list(self._tasks):
                    task.cancel()
                break
            if text == "/new":
                self._thread += 1
                self._write(f"(conversation {self._thread})")
                continue
            if text == "/stop":
                await inbound.cancel(self._binding(), self.ACCOUNT)
                continue
            # Not awaited: while a turn waits for an approval, the answer must still
            # be read from the next line.
            message = InboundMessage(binding=self._binding(), sender=self.ACCOUNT, text=text)
            task = asyncio.create_task(inbound.handle(message))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def send(self, binding: ChannelBinding, text: str) -> None:
        self._write(f"\nai-os> {text}\n")

    async def start_thread(self, address: str, text: str) -> ChannelBinding:
        self._started += 1
        self._write(f"\n{text}")
        return ChannelBinding(
            channel=self.name, address=address, thread=f"run-{int(time.time())}-{self._started}"
        )

    async def report(self, binding: ChannelBinding, event: ProgressEvent) -> None:
        self._write(f"  · {event.label}")

    async def finish(self, binding: ChannelBinding) -> None:
        return None

    @staticmethod
    def _print(text: str) -> None:
        print(text, flush=True)

    def _binding(self) -> ChannelBinding:
        return ChannelBinding(channel=self.name, address="local", thread=str(self._thread))
