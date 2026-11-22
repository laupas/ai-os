import asyncio
import logging
from typing import Any

from aios.approvals.approval_answer_handler import ApprovalAnswerHandler
from aios.approvals.approval_presenter import ApprovalPresenter
from aios.channels.authored_sender import AuthoredSender
from aios.channels.message_channel import MessageChannel
from aios.channels.message_chunker import MessageChunker
from aios.channels.teams.teams_activity_reader import TeamsActivityReader
from aios.channels.teams.teams_bot import TeamsBot
from aios.channels.teams.teams_cards import STOP, TeamsCards
from aios.channels.teams.teams_emoji import TeamsEmoji
from aios.channels.teams.teams_status_tracker import TeamsStatusTracker
from aios.channels.teams.teams_threads import TeamsThreads
from aios.channels.teams.teams_voice_notes import TeamsVoiceNotes
from aios.channels.thread_starter import ThreadStarter
from aios.conversations.inbound_handler import InboundHandler
from aios.conversations.inbound_message import InboundMessage
from aios.entities.approvals.approval import Approval
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.user import User
from aios.progress.progress_event import ProgressEvent
from aios.progress.progress_reporter import ProgressReporter

log = logging.getLogger(__name__)

DEFAULT_SERVICE_URL = "https://smba.trafficmanager.net/teams"
NEW_COMMAND = "/new"
NEW_STARTED = "Started a new conversation."
NEW_IN_THREADS = (
    "Write at the top of the chat to start a new conversation: each one gets its own thread."
)
NO_VOICE = "I could not listen to that voice note."
CANNOT_ANSWER = "You can't answer this one: it is no longer pending, or you may not approve it."


class TeamsChannel(
    MessageChannel, ProgressReporter, ApprovalPresenter, ThreadStarter, AuthoredSender
):
    """Microsoft Teams over the Teams SDK's Socket Mode: outbound connection only,
    no public address needed (see `TeamsBot`).

    A post in a Teams channel is a conversation per thread; so is a message at the
    top of a personal or group chat with threads in chats on, else the chat is one
    conversation until `/new` (see `TeamsThreads`). Who may talk is
    decided by the gateway from the users' Teams accounts (Entra object ids).
    A bot can only post as itself, so a user's words from another channel are
    labelled with their name.

    If Teams cannot be reached, this channel logs it and stays idle rather than
    ending: the first channel to end stops the whole application.
    """

    def __init__(
        self,
        tenant_id: str,
        bot: TeamsBot,
        threads: TeamsThreads,
        cards: TeamsCards,
        emoji: TeamsEmoji,
        chunker: MessageChunker,
        voice_notes: TeamsVoiceNotes,
    ) -> None:
        self._tenant_id = tenant_id
        self._bot = bot
        self._threads = threads
        self._cards = cards
        self._emoji = emoji
        self._chunker = chunker
        self._voice_notes = voice_notes
        self._status = TeamsStatusTracker(bot, cards, threads)
        self._service_urls: dict[str, str] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    @property
    def name(self) -> str:
        return "teams"

    async def start(self, inbound: InboundHandler, answers: ApprovalAnswerHandler) -> None:
        reader = TeamsActivityReader(self._threads, inbound.is_known)

        async def on_activity(activity: dict[str, Any]) -> None:
            # Teams wants each activity acknowledged within 25 s; turns take longer.
            self._spawn(self._dispatch(inbound, answers, reader, activity))

        try:
            log.info("teams connecting in socket mode")
            await self._bot.run(on_activity)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("teams could not connect; the other channels go on without it")
        else:
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError  # ai-os is ending: idling would keep it alive
            log.error("teams stopped receiving; the other channels go on without it")
        await asyncio.Event().wait()

    async def send(self, binding: ChannelBinding, text: str) -> None:
        service_url = self._service_url_for(binding.address)
        conversation_id = TeamsThreads.conversation_id(binding)
        reply_chain = self._threads.reply_chain(binding)
        for chunk in self._chunker.split(self._emoji.convert(text)):
            sent = await self._bot.send_text(
                service_url, conversation_id, chunk, reply_chain, self._threads.take_quote(binding)
            )
            self._threads.remember(sent, binding)

    async def send_as(self, binding: ChannelBinding, text: str, author: User, via: str) -> None:
        await self.send(binding, f"**{author.name} ({via}):** {text}")

    async def start_thread(self, address: str, text: str) -> ChannelBinding:
        """`address` is a user's Entra object id: posts at the top of the personal chat
        with them, which needs the app installed for them, and starts a new
        conversation there (in the post's thread, with threads in chats)."""
        conversation_id = await self._bot.open_personal_chat(self._tenant_id, address.lower())
        activity_id = await self._bot.send_text(
            self._service_url_for(conversation_id), conversation_id, self._emoji.convert(text)
        )
        binding = self._threads.restart(conversation_id, activity_id)
        self._threads.quote_next(binding, activity_id)
        return binding

    async def report(self, binding: ChannelBinding, event: ProgressEvent) -> None:
        await self._status.add(binding, self._service_url_for(binding.address), event.label)

    async def finish(self, binding: ChannelBinding) -> None:
        await self._status.finish(binding, self._service_url_for(binding.address))

    async def present(self, approval: Approval) -> None:
        binding = approval.binding
        card_id = await self._bot.send_card(
            self._service_url_for(binding.address),
            TeamsThreads.conversation_id(binding),
            self._cards.approval(approval),
            approval.question,
            self._threads.reply_chain(binding),
        )
        self._threads.remember(card_id, binding)

    async def _dispatch(
        self,
        inbound: InboundHandler,
        answers: ApprovalAnswerHandler,
        reader: TeamsActivityReader,
        activity: dict[str, Any],
    ) -> None:
        try:
            self._remember_service_url(activity)
            action = self._cards.read_action(activity.get("value"))
            if activity.get("type") == "message" and action is not None:
                await self._on_button(inbound, answers, activity, action)
                return
            message = reader.read(activity)
            if message is None:
                return
            if message.text == NEW_COMMAND and TeamsThreads.is_chat(message.binding):
                if self._threads.reply_chain(message.binding):
                    await self.send(message.binding, NEW_IN_THREADS)
                    return
                binding = self._threads.restart(message.binding.address, str(activity["id"]))
                await self.send(binding, NEW_STARTED)
                return
            await self._receive(inbound, message)
        except Exception:
            log.exception("teams: handling an activity failed")

    async def _on_button(
        self,
        inbound: InboundHandler,
        answers: ApprovalAnswerHandler,
        activity: dict[str, Any],
        action: dict[str, Any],
    ) -> None:
        sender = TeamsActivityReader.sender_of(activity)
        if sender is None:
            return
        binding = self._threads.binding_of(activity)
        if action["aios"] == STOP:
            await inbound.cancel(binding, sender)
            return
        answer = str(action.get("answer", ""))
        accepted = await answers.answer(str(action.get("approval_id", "")), answer, sender)
        card_id = activity.get("replyToId")
        if not accepted:
            await self.send(binding, CANNOT_ANSWER)
        elif card_id:
            by = str((activity.get("from") or {}).get("name") or "someone")
            await self._bot.update_card(
                self._service_url_for(binding.address),
                TeamsThreads.conversation_id(binding),
                str(card_id),
                self._cards.answered(str(action.get("question", "")), answer, by),
                answer,
            )

    async def _receive(self, inbound: InboundHandler, message: InboundMessage) -> None:
        if self._voice_notes.audio_in(message) is not None:
            try:
                message, transcript = await self._voice_notes.transcribe(message)
            except Exception as exc:
                log.warning("voice note failed: %s", exc)
                transcript = None
            if transcript:
                await self.send(message.binding, f"🎙️ {transcript}")
            elif not message.text:
                await self.send(message.binding, NO_VOICE)
        if message.text:
            await inbound.handle(message)

    def _remember_service_url(self, activity: dict[str, Any]) -> None:
        service_url = activity.get("serviceUrl")
        conversation = activity.get("conversation") or {}
        if service_url and conversation.get("id"):
            address = self._threads.binding_of(activity).address
            self._service_urls[address] = str(service_url)

    def _service_url_for(self, address: str) -> str:
        return self._service_urls.get(address, DEFAULT_SERVICE_URL)

    def _spawn(self, coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
