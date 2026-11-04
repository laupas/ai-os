import asyncio
import logging
import re
from typing import Any

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from aios.approvals.approval_answer_handler import ApprovalAnswerHandler
from aios.approvals.approval_presenter import ApprovalPresenter
from aios.channels.authored_sender import AuthoredSender
from aios.channels.message_channel import MessageChannel
from aios.channels.slack.markdown_to_mrkdwn import MarkdownToMrkdwn
from aios.channels.slack.message_chunker import MessageChunker
from aios.channels.slack.slack_blocks import APPROVAL_ACTION_PREFIX, STOP_ACTION, SlackBlocks
from aios.channels.slack.slack_event_reader import SlackEventReader
from aios.channels.slack.slack_status_tracker import SlackStatusTracker
from aios.channels.slack.slack_voice_notes import SlackVoiceNotes
from aios.channels.thread_starter import ThreadStarter
from aios.conversations.inbound_handler import InboundHandler
from aios.conversations.inbound_message import InboundMessage
from aios.entities.approvals.approval import Approval
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.user import User
from aios.progress.progress_event import ProgressEvent
from aios.progress.progress_reporter import ProgressReporter

log = logging.getLogger(__name__)

NO_VOICE = "I could not listen to that voice note."
CANNOT_ANSWER = "You can't answer this one: it is no longer pending, or you may not approve it."


class SlackChannel(
    MessageChannel, ProgressReporter, ApprovalPresenter, ThreadStarter, AuthoredSender
):
    """Slack over Socket Mode: outbound connection only, no public URL needed.

    Each thread is a conversation. Who may talk is decided by the gateway from the
    users' Slack accounts, not here.

    A bot token can only post as the bot. With the `chat:write.customize` scope it
    may set a name and picture per message, which is how a user's words typed on
    another channel are shown as theirs; without it they are labelled instead.
    """

    def __init__(
        self,
        bot_token: str | None,
        app_token: str | None,
        blocks: SlackBlocks,
        converter: MarkdownToMrkdwn,
        chunker: MessageChunker,
        voice_notes: SlackVoiceNotes,
    ) -> None:
        if not bot_token or not app_token:
            raise RuntimeError("Slack needs SLACK_BOT_TOKEN and SLACK_APP_TOKEN")
        self._app_token = app_token
        self._client = AsyncWebClient(token=bot_token)
        self._blocks = blocks
        self._converter = converter
        self._chunker = chunker
        self._voice_notes = voice_notes
        self._status = SlackStatusTracker(self._client, blocks)
        self._tasks: set[asyncio.Task[None]] = set()
        self._can_customize: bool | None = None
        self._avatars: dict[str, str | None] = {}

    @property
    def name(self) -> str:
        return "slack"

    async def start(self, inbound: InboundHandler, answers: ApprovalAnswerHandler) -> None:
        app = AsyncApp(client=self._client)
        bot_user_id = str((await self._client.auth_test())["user_id"])
        reader = SlackEventReader(bot_user_id, inbound.is_known)

        @app.event("message")
        async def on_message(event: dict[str, Any]) -> None:
            message = reader.read(event)
            if message is not None:
                self._spawn(self._receive(inbound, message))

        @app.action(re.compile(f"^{APPROVAL_ACTION_PREFIX}"))
        async def on_approval(ack: Any, body: dict[str, Any], action: dict[str, Any]) -> None:
            await ack()
            await self._answer(answers, body, action)

        @app.action(STOP_ACTION)
        async def on_stop(ack: Any, body: dict[str, Any]) -> None:
            await ack()
            binding = self._blocks.binding_of(body["channel"]["id"], body["message"])
            sender = ChannelAccount(channel="slack", address=body["user"]["id"])
            await inbound.cancel(binding, sender)

        log.info("slack connected as %s", bot_user_id)
        await AsyncSocketModeHandler(app, self._app_token).start_async()

    async def send(self, binding: ChannelBinding, text: str) -> None:
        for chunk in self._chunker.split(self._converter.convert(text)):
            await self._client.chat_postMessage(
                channel=binding.address, thread_ts=binding.thread, text=chunk
            )

    async def send_as(self, binding: ChannelBinding, text: str, author: User, via: str) -> None:
        if not await self._customizable():
            await self.send(binding, f"*{author.name} ({via}):* {text}")
            return
        account = author.account_for(self.name)
        avatar = await self._avatar(account.address) if account else None
        for chunk in self._chunker.split(self._converter.convert(text)):
            await self._client.chat_postMessage(
                channel=binding.address,
                thread_ts=binding.thread,
                text=chunk,
                username=f"{author.name} ({via})",
                icon_url=avatar,
            )

    async def _customizable(self) -> bool:
        if self._can_customize is None:
            try:
                response = await self._client.auth_test()
                scopes = str(response.headers.get("x-oauth-scopes", "")).split(",")
                self._can_customize = "chat:write.customize" in {s.strip() for s in scopes}
            except Exception:
                log.exception("could not read the Slack token's scopes")
                return False
        return self._can_customize

    async def _avatar(self, slack_user_id: str) -> str | None:
        if slack_user_id not in self._avatars:
            try:
                profile = (await self._client.users_info(user=slack_user_id))["user"]["profile"]
                self._avatars[slack_user_id] = profile.get("image_72")
            except Exception:
                self._avatars[slack_user_id] = None  # users:read missing, or no such user
        return self._avatars[slack_user_id]

    async def start_thread(self, address: str, text: str) -> ChannelBinding:
        """`address` is a channel id, or a user id to post into the DM with them."""
        response = await self._client.chat_postMessage(channel=address, text=text)
        return ChannelBinding(
            channel=self.name, address=str(response["channel"]), thread=str(response["ts"])
        )

    async def report(self, binding: ChannelBinding, event: ProgressEvent) -> None:
        await self._status.add(binding, event.label)

    async def finish(self, binding: ChannelBinding) -> None:
        await self._status.finish(binding)

    async def present(self, approval: Approval) -> None:
        await self._client.chat_postMessage(
            channel=approval.binding.address,
            thread_ts=approval.binding.thread,
            text=approval.question,
            blocks=self._blocks.approval(approval),
        )

    async def _receive(self, inbound: InboundHandler, message: InboundMessage) -> None:
        if self._voice_notes.audio_in(message) is not None:
            try:
                message, transcript = await self._voice_notes.transcribe(message)
            except Exception as exc:
                log.warning("voice note failed: %s", exc)
                transcript = None
            if transcript:
                await self.send(message.binding, f":studio_microphone: {transcript}")
            elif not message.text:
                await self.send(message.binding, NO_VOICE)
        if message.text:
            await inbound.handle(message)

    async def _answer(
        self, answers: ApprovalAnswerHandler, body: dict[str, Any], action: dict[str, Any]
    ) -> None:
        approval_id, answer = self._blocks.read_approval_value(action["value"])
        user_id, channel_id = body["user"]["id"], body["channel"]["id"]
        accepted = await answers.answer(
            approval_id, answer, ChannelAccount(channel="slack", address=user_id)
        )
        if accepted:
            question = body["message"].get("text", "")
            await self._client.chat_update(
                channel=channel_id,
                ts=body["message"]["ts"],
                text=f"{question} → {answer}",
                blocks=self._blocks.answered(question, answer, user_id),
            )
        else:
            await self._client.chat_postEphemeral(
                channel=channel_id, user=user_id, text=CANNOT_ANSWER
            )

    def _spawn(self, coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
