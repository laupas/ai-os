import asyncio
import logging

from aios.approvals.approval_service import ApprovalService
from aios.channels.channel_directory import ChannelDirectory
from aios.conversations.conversation_delivery import ConversationDelivery
from aios.conversations.conversation_event import ConversationEvent
from aios.conversations.conversation_lock_manager import ConversationLockManager
from aios.conversations.conversation_observer import ConversationObserver
from aios.conversations.conversation_resolver import ConversationResolver
from aios.conversations.inbound_handler import InboundHandler
from aios.conversations.inbound_message import InboundMessage
from aios.conversations.message_recorder import MessageRecorder
from aios.conversations.turn_canceller import TurnCanceller
from aios.conversations.turn_starter import TurnStarter
from aios.engine.agent_engine import AgentEngine
from aios.engine.text_delta import TextDelta
from aios.engine.turn_request import TurnRequest
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.conversation import Conversation
from aios.entities.conversations.message_role import MessageRole
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.progress.progress_event import ProgressEvent
from aios.storage.collection import Collection
from aios.users.authorizer import Authorizer

log = logging.getLogger(__name__)

NOT_ALLOWED = "Sorry, you are not allowed to use ai-os."
STOPPED = "Stopped."


class Gateway(InboundHandler, TurnStarter):
    """Inbound message -> who is it -> which conversation -> agent turn -> reply.

    A conversation may live in several places (a Slack thread and the web console):
    the reply, progress and the user's own message go to all of them through
    `ConversationDelivery`. `observers` see each turn's progress, its streamed text
    and its end; the messages themselves reach them from the `MessageRecorder`.
    """

    def __init__(
        self,
        users: Collection[User],
        authorizer: Authorizer,
        resolver: ConversationResolver,
        recorder: MessageRecorder,
        locks: ConversationLockManager,
        canceller: TurnCanceller,
        engine: AgentEngine,
        channels: ChannelDirectory,
        approvals: ApprovalService,
        observers: list[ConversationObserver] | None = None,
        delivery: ConversationDelivery | None = None,
    ) -> None:
        self._users = users
        self._authorizer = authorizer
        self._resolver = resolver
        self._recorder = recorder
        self._locks = locks
        self._canceller = canceller
        self._engine = engine
        self._channels = channels
        self._approvals = approvals
        self._observers = list(observers or [])
        self._delivery = delivery or ConversationDelivery(channels)

    async def handle(self, message: InboundMessage) -> None:
        user = self._chat_user(message.sender)
        if user is None:
            log.warning(
                "refused message from %s:%s", message.sender.channel, message.sender.address
            )
            await self._channels.get(message.binding.channel).send(message.binding, NOT_ALLOWED)
            return
        known = self._resolver.find(message.binding)
        if known is not None and await self._approvals.answer_from_text(
            known.id, message.sender, message.text
        ):
            return
        await self._converse(user, message.binding, message.text)

    async def start_turn(
        self, user: User, bindings: list[ChannelBinding], text: str, agent: str | None = None
    ) -> None:
        if not self._authorizer.has(user, Permission.CHAT):
            log.warning("not starting a turn for %s: no chat permission", user.id)
            return
        conversation = await self._resolver.resolve(bindings[0], user, agent)
        for binding in bindings[1:]:
            conversation = await self._resolver.attach(conversation, binding)
        await self._converse(user, bindings[0], text, mirror=False)

    async def cancel(self, binding: ChannelBinding, sender: ChannelAccount) -> bool:
        if self._chat_user(sender) is None:
            return False
        conversation = self._resolver.find(binding)
        return conversation is not None and self._canceller.cancel(conversation.id)

    def is_known(self, binding: ChannelBinding) -> bool:
        return self._resolver.find(binding) is not None

    async def _converse(
        self, user: User, binding: ChannelBinding, text: str, mirror: bool = True
    ) -> None:
        conversation = await self._resolver.resolve(binding, user)
        await self._recorder.record(
            conversation.id, MessageRole.USER, text, binding.channel, user.id
        )
        if mirror:
            await self._delivery.mirror(conversation, binding, user, text)
        async with self._locks.lock_for(conversation.id):
            task = asyncio.create_task(self._run_turn(conversation.id, user, binding, text))
            self._canceller.track(conversation.id, task)
            try:
                await task
            except asyncio.CancelledError:
                current = asyncio.current_task()
                if current is not None and current.cancelling():
                    raise  # we are shutting down, not a Stop from the user
                await self._reply(conversation.id, STOPPED, binding.channel)
            finally:
                self._canceller.forget(conversation.id)

    def _chat_user(self, sender: ChannelAccount) -> User | None:
        user = self._users.find(lambda u: u.has_account(sender.channel, sender.address))
        return user if self._authorizer.has(user, Permission.CHAT) else None

    async def _run_turn(
        self, conversation_id: str, user: User, binding: ChannelBinding, text: str
    ) -> None:
        # Re-read under the lock: the previous turn may have stored a new session id.
        conversation = self._resolver.find(binding)
        assert conversation is not None and conversation.id == conversation_id

        steps: list[str] = []

        async def on_progress(event: ProgressEvent) -> None:
            if not steps or steps[-1] != event.label:
                steps.append(event.label)
            await self._delivery.report(conversation, event)
            self._notify(conversation_id, "progress", text=event.label)

        async def on_text(delta: TextDelta) -> None:
            self._notify(conversation_id, "delta", text=delta.text, restart=delta.restart)

        failure: Exception | None = None
        try:
            result = await self._engine.run_turn(
                TurnRequest(conversation=conversation, user=user, binding=binding, text=text),
                on_progress,
                on_text if self._observers else None,
            )
        except Exception as exc:
            log.exception("turn failed in conversation %s", conversation_id)
            failure = exc
        finally:
            await self._delivery.finish(conversation)
            self._notify(conversation_id, "done")
            if steps:  # before the reply, where it happened
                await self._recorder.record(
                    conversation_id, MessageRole.ACTIVITY, "\n".join(steps), binding.channel
                )
        if failure is not None:
            await self._reply(conversation_id, f"Something went wrong: {failure}", binding.channel)
            return
        await self._remember_session(conversation, result.session_id)
        await self._reply(conversation_id, result.text, binding.channel)

    def _notify(self, conversation_id: str, kind: str, **fields: object) -> None:
        event = ConversationEvent(conversation_id=conversation_id, kind=kind, **fields)  # type: ignore[arg-type]
        for observer in self._observers:
            observer.notify(event)

    async def _remember_session(self, conversation: Conversation, session_id: str | None) -> None:
        if session_id and session_id != conversation.agent_session_id:
            await self._resolver.save(
                conversation.model_copy(update={"agent_session_id": session_id})
            )

    async def _reply(self, conversation_id: str, text: str, channel: str) -> None:
        """`channel` is where the turn was asked from; the reply goes everywhere."""
        conversation = self._resolver.get(conversation_id)
        if conversation is not None:
            await self._delivery.send(conversation, text)
        await self._recorder.record(conversation_id, MessageRole.ASSISTANT, text, channel)
