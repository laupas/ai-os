import asyncio
from typing import Any

from aios.approvals.approval_answer_handler import ApprovalAnswerHandler
from aios.channels.message_channel import MessageChannel
from aios.channels.thread_starter import ThreadStarter
from aios.common.id_generator import IdGenerator
from aios.conversations.inbound_handler import InboundHandler
from aios.conversations.inbound_message import InboundMessage
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.channel_account import ChannelAccount


class WebChannel(MessageChannel, ThreadStarter):
    """Chat in the web console. The HTTP side lives in `aios/web`; this is the
    channel half, which hands typed messages to the gateway.

    It sends nothing itself: messages, progress, streamed text and approvals reach
    the browser through `WebEventHub`, which sees every conversation whatever else
    it is bound to.

    A binding's `address` is the user's web account (their Access email) and its
    `thread` a fresh id, or the conversation's id when the web joins a conversation
    that started elsewhere.
    """

    def __init__(self, ids: IdGenerator) -> None:
        self._ids = ids
        self._inbound: InboundHandler | None = None
        self._tasks: set[asyncio.Task[None]] = set()

    @property
    def name(self) -> str:
        return "web"

    @property
    def ready(self) -> bool:
        """Whether the channel was started, i.e. is enabled in config."""
        return self._inbound is not None

    async def start(self, inbound: InboundHandler, answers: ApprovalAnswerHandler) -> None:
        self._inbound = inbound
        await asyncio.Event().wait()  # the web server does the work; run for ever

    def new_binding(self, account: ChannelAccount) -> ChannelBinding:
        return ChannelBinding(channel=self.name, address=account.address, thread=self._ids.new_id())

    def submit(self, binding: ChannelBinding, sender: ChannelAccount, text: str) -> None:
        """Not awaited by the caller: a turn can wait for an approval, which is
        answered by a later request."""
        assert self._inbound is not None, "web channel not started"
        message = InboundMessage(binding=binding, sender=sender, text=text)
        self._spawn(self._inbound.handle(message))

    async def cancel(self, binding: ChannelBinding, sender: ChannelAccount) -> bool:
        assert self._inbound is not None, "web channel not started"
        return await self._inbound.cancel(binding, sender)

    async def send(self, binding: ChannelBinding, text: str) -> None:
        return None  # recorded messages reach the browser through the hub

    async def start_thread(self, address: str, text: str) -> ChannelBinding:
        return ChannelBinding(channel=self.name, address=address, thread=self._ids.new_id())

    def _spawn(self, coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
