import asyncio
from typing import Any

from aios.approvals.approval_answer_handler import ApprovalAnswerHandler
from aios.channels.message_chunker import MessageChunker
from aios.channels.teams.teams_cards import TeamsCards
from aios.channels.teams.teams_channel import (
    CANNOT_ANSWER,
    DEFAULT_SERVICE_URL,
    NEW_IN_THREADS,
    NEW_STARTED,
    NO_VOICE,
    NO_VOICE_RIGHT,
    TeamsChannel,
)
from aios.channels.teams.teams_emoji import TeamsEmoji
from aios.channels.teams.teams_threads import TeamsThreads
from aios.channels.teams.teams_voice_notes import TeamsVoiceNotes
from aios.conversations.inbound_handler import InboundHandler
from aios.conversations.inbound_message import InboundMessage
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.permission import Permission
from aios.progress.progress_event import ProgressEvent
from aios.users.voice_gate import VoiceGate
from tests.fakes.world import World

SERVICE = "https://smba.trafficmanager.net/emea/"


class FakeBot:
    """Stands in for `TeamsBot`: delivers activities and records what is sent."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.chains: list[tuple[str, str] | None] = []
        self.quotes: list[str | None] = []
        self.on_activity: Any = None
        self.texts: list[tuple[str, str, str]] = []
        self.cards: list[tuple[str, str, dict[str, Any]]] = []
        self.updates: list[tuple[str, str, str, dict[str, Any]]] = []
        self.opened: list[tuple[str, str]] = []
        self.running = asyncio.Event()

    async def run(self, on_activity: Any) -> None:
        if self.fail:
            raise RuntimeError("Socket Mode negotiate failed: HTTP 403.")
        self.on_activity = on_activity
        self.running.set()
        await asyncio.Event().wait()

    async def send_text(self, service_url, conversation_id, text, reply_chain=None, quote=None):
        self.texts.append((service_url, conversation_id, text))
        self.chains.append(reply_chain)
        self.quotes.append(quote)
        return f"act{len(self.texts)}"

    async def send_card(self, service_url, conversation_id, card, summary, reply_chain=None):
        self.cards.append((service_url, conversation_id, card))
        self.chains.append(reply_chain)
        self.quotes.append(None)
        return f"card{len(self.cards)}"

    async def update_card(self, service_url, conversation_id, activity_id, card, summary) -> None:
        self.updates.append((service_url, conversation_id, activity_id, card))

    async def open_personal_chat(self, tenant_id: str, user_id: str) -> str:
        self.opened.append((tenant_id, user_id))
        return "a:new-chat"


class FakeInbound(InboundHandler):
    def __init__(self) -> None:
        self.handled: list[InboundMessage] = []
        self.cancelled: list[tuple[ChannelBinding, ChannelAccount]] = []

    async def handle(self, message: InboundMessage) -> None:
        self.handled.append(message)

    async def cancel(self, binding: ChannelBinding, sender: ChannelAccount) -> bool:
        self.cancelled.append((binding, sender))
        return True

    def is_known(self, binding: ChannelBinding) -> bool:
        return False


class FakeAnswers(ApprovalAnswerHandler):
    def __init__(self, accept: bool = True) -> None:
        self.accept = accept
        self.answers: list[tuple[str, str, ChannelAccount]] = []

    async def answer(self, approval_id: str, answer: str, sender: ChannelAccount) -> bool:
        self.answers.append((approval_id, answer, sender))
        return self.accept


class NoTranscriber:
    def is_available(self) -> bool:
        return False


def _gate(world: World | None = None) -> VoiceGate:
    """Over `world`'s users; without one, a gate that knows nobody."""
    w = world or World()
    return VoiceGate(w.users, w.authorizer)


def _channel(bot: FakeBot, in_chats: bool = False, gate: VoiceGate | None = None) -> TeamsChannel:
    return TeamsChannel(
        tenant_id="tenant",
        bot=bot,  # type: ignore[arg-type]
        threads=TeamsThreads(in_chats=in_chats),
        cards=TeamsCards(),
        emoji=TeamsEmoji(),
        chunker=MessageChunker(size=1000),
        voice_notes=TeamsVoiceNotes(NoTranscriber(), gate or _gate()),  # type: ignore[arg-type]
    )


def _activity(**overrides: object) -> dict[str, Any]:
    activity: dict[str, Any] = {
        "type": "message",
        "id": "m1",
        "serviceUrl": SERVICE,
        "from": {"id": "29:user", "aadObjectId": "user-oid", "name": "Ada"},
        "recipient": {"id": "28:bot"},
        "conversation": {"id": "a:chat", "conversationType": "personal"},
        "text": "hi",
    }
    activity.update(overrides)
    return activity


async def _started(channel: TeamsChannel, bot: FakeBot, inbound=None, answers=None):
    task = asyncio.create_task(channel.start(inbound or FakeInbound(), answers or FakeAnswers()))
    await asyncio.wait_for(bot.running.wait(), 1)
    return task


async def _deliver(channel: TeamsChannel, bot: FakeBot, activity: dict[str, Any]) -> None:
    await bot.on_activity(activity)
    await asyncio.gather(*list(channel._tasks))


async def test_a_message_is_handed_on_and_replies_go_to_its_service_url() -> None:
    bot, inbound = FakeBot(), FakeInbound()
    channel = _channel(bot)
    task = await _started(channel, bot, inbound=inbound)
    await _deliver(channel, bot, _activity())
    assert inbound.handled[0].text == "hi"
    await channel.send(inbound.handled[0].binding, ":white_check_mark: done")
    assert bot.texts == [(SERVICE, "a:chat", "✅ done")]
    task.cancel()


async def test_new_starts_another_conversation_in_the_chat() -> None:
    bot, inbound = FakeBot(), FakeInbound()
    channel = _channel(bot)
    task = await _started(channel, bot, inbound=inbound)
    await _deliver(channel, bot, _activity(id="m7", text="/new"))
    assert not inbound.handled and bot.texts[0][2] == NEW_STARTED
    await _deliver(channel, bot, _activity(id="m8"))
    assert inbound.handled[0].binding.thread == "chat-m7"
    task.cancel()


async def test_an_approval_button_answers_and_updates_its_card() -> None:
    bot, answers = FakeBot(), FakeAnswers()
    channel = _channel(bot)
    task = await _started(channel, bot, answers=answers)
    value = {"aios": "approval", "approval_id": "ap1", "answer": "Yes", "question": "Send?"}
    await _deliver(channel, bot, _activity(value=value, replyToId="card1"))
    assert answers.answers == [("ap1", "Yes", ChannelAccount(channel="teams", address="user-oid"))]
    assert bot.updates[0][2] == "card1"
    task.cancel()


async def test_a_refused_answer_is_said_and_stop_cancels() -> None:
    bot, inbound = FakeBot(), FakeInbound()
    channel = _channel(bot)
    task = await _started(channel, bot, inbound=inbound, answers=FakeAnswers(accept=False))
    value = {"aios": "approval", "approval_id": "ap1", "answer": "Yes", "question": "Send?"}
    await _deliver(channel, bot, _activity(value=value))
    assert bot.texts[0][2] == CANNOT_ANSWER
    await _deliver(channel, bot, _activity(value={"aios": "stop"}))
    assert inbound.cancelled[0][0].thread == "chat"
    task.cancel()


async def test_progress_is_one_card_edited_in_place() -> None:
    bot = FakeBot()
    channel = _channel(bot)
    binding = ChannelBinding(channel="teams", address="a:chat", thread="chat")
    await channel.report(binding, ProgressEvent(label="Reading mail", tool_name="x"))
    await channel.report(binding, ProgressEvent(label="Writing", tool_name="y"))
    await channel.finish(binding)
    assert len(bot.cards) == 1 and bot.cards[0][0] == DEFAULT_SERVICE_URL
    assert [u[2] for u in bot.updates] == ["card1", "card1"]
    assert bot.updates[-1][3]["actions"] == []  # no Stop once done


async def test_a_scheduled_thread_opens_the_personal_chat_as_a_new_conversation() -> None:
    bot = FakeBot()
    binding = await _channel(bot).start_thread("USER-OID", ":alarm_clock: Daily")
    assert bot.opened == [("tenant", "user-oid")]
    assert bot.texts[0][2] == "⏰ Daily"
    assert binding == ChannelBinding(channel="teams", address="a:new-chat", thread="chat-act1")


def _in_thread(root: str, **overrides: object) -> dict[str, Any]:
    channel_data = {"replyChain": {"id": root}, "chat": {"id": "19:chat@unq.gbl.spaces"}}
    return _activity(channelData=channel_data, **overrides)


async def test_with_threads_each_top_message_is_a_conversation_answered_in_its_thread() -> None:
    bot, inbound = FakeBot(), FakeInbound()
    channel = _channel(bot, in_chats=True)
    task = await _started(channel, bot, inbound=inbound)
    await _deliver(channel, bot, _in_thread("1700", id="1700"))
    await _deliver(channel, bot, _in_thread("1700", id="1705", text="more"))
    await _deliver(channel, bot, _in_thread("1800", id="1800", text="other"))
    first, more, other = (m.binding for m in inbound.handled)
    assert first == more == ChannelBinding(channel="teams", address="a:chat", thread="chat-1700")
    assert other.thread == "chat-1800"
    await channel.send(first, "answer")
    await channel.report(first, ProgressEvent(label="Reading mail", tool_name="x"))
    assert bot.texts == [(SERVICE, "a:chat", "answer")]
    assert bot.chains == [("19:chat@unq.gbl.spaces", "1700")] * 2
    task.cancel()


async def test_with_threads_a_button_belongs_to_the_thread_of_its_card() -> None:
    bot, inbound = FakeBot(), FakeInbound()
    channel = _channel(bot, in_chats=True)
    task = await _started(channel, bot, inbound=inbound)
    await _deliver(channel, bot, _in_thread("1700", id="f:guid", value={"aios": "stop"}))
    assert inbound.cancelled[0][0].thread == "chat-1700"
    task.cancel()


async def test_with_threads_new_explains_instead_of_restarting() -> None:
    bot, inbound = FakeBot(), FakeInbound()
    channel = _channel(bot, in_chats=True)
    task = await _started(channel, bot, inbound=inbound)
    await _deliver(channel, bot, _in_thread("1700", id="1705", text="/new"))
    assert not inbound.handled and bot.texts[0][2] == NEW_IN_THREADS
    assert bot.chains == [("19:chat@unq.gbl.spaces", "1700")]
    task.cancel()


async def test_with_threads_a_scheduled_post_is_the_top_of_its_thread() -> None:
    bot = FakeBot()
    channel = _channel(bot, in_chats=True)
    binding = await channel.start_thread("USER-OID", "Daily")
    assert bot.chains == [None]  # the post itself is at the top
    assert binding.thread == "chat-act1"
    numeric = binding.model_copy(update={"thread": "chat-1900"})
    await channel.send(numeric, "result")
    assert bot.chains == [None, ("a:new-chat", "1900")]  # chat id not known yet


async def test_without_threads_a_chat_ignores_reply_chains() -> None:
    bot, inbound = FakeBot(), FakeInbound()
    channel = _channel(bot)
    task = await _started(channel, bot, inbound=inbound)
    await _deliver(channel, bot, _in_thread("1700", id="1705"))
    assert inbound.handled[0].binding.thread == "chat"
    await channel.send(inbound.handled[0].binding, "answer")
    assert bot.chains == [None]
    task.cancel()


async def test_a_scheduled_run_quotes_its_post_in_the_answer_once() -> None:
    bot = FakeBot()
    channel = _channel(bot)
    binding = await channel.start_thread("USER-OID", "Daily")
    binding = binding.model_copy(update={"thread": "chat-1900"})
    channel._threads.quote_next(binding, "1900")
    await channel.report(binding, ProgressEvent(label="Reading mail", tool_name="x"))
    await channel.send(binding, "result")
    await channel.send(binding, "more")
    assert bot.quotes == [None, None, "1900", None]  # the post, the card, the answer, more


async def test_a_quoted_message_is_quoted_in_the_answer() -> None:
    bot, inbound = FakeBot(), FakeInbound()
    channel = _channel(bot)
    task = await _started(channel, bot, inbound=inbound)
    started = channel._threads.restart("a:chat", "1500")
    channel._threads.remember("1501", started)
    quote = {"type": "quotedReply", "quotedReply": {"messageId": "1501"}}
    await _deliver(channel, bot, _activity(id="1600", entities=[quote]))
    await _deliver(channel, bot, _activity(id="1601", text="plain"))
    assert [m.binding for m in inbound.handled] == [started, started]
    await channel.send(started, "answer")
    await channel.send(started, "another")
    assert bot.quotes == ["1600", None]
    task.cancel()


async def test_a_failing_connection_does_not_end_the_channel() -> None:
    bot = FakeBot(fail=True)
    task = asyncio.create_task(_channel(bot).start(FakeInbound(), FakeAnswers()))
    await asyncio.sleep(0.05)
    assert not task.done()  # ending would stop every other channel
    task.cancel()


async def test_the_channel_ends_when_ai_os_ends_even_if_the_bot_swallows_the_cancel() -> None:
    class SwallowingBot(FakeBot):
        async def run(self, on_activity: Any) -> None:
            self.running.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return

    bot = SwallowingBot()
    task = asyncio.create_task(_channel(bot).start(FakeInbound(), FakeAnswers()))
    await asyncio.wait_for(bot.running.wait(), 1)
    task.cancel()
    await asyncio.wait({task}, timeout=1)
    assert task.cancelled()  # idling here kept ai-os from ending, and so from restarting


def _voice_note() -> dict[str, Any]:
    file = {
        "contentType": "application/vnd.microsoft.teams.file.download.info",
        "name": "note.m4a",
        "content": {"downloadUrl": "https://files.example/note.m4a"},
    }
    return _activity(text="", attachments=[file])


async def _bob_on_teams(*group_ids: str) -> World:
    """Bob, whose Teams account sends `_activity`, in `group_ids`."""
    w = await World().setup()
    teams = ChannelAccount(channel="teams", address="user-oid")
    await w.users.put(
        w.bob.model_copy(
            update={"accounts": [*w.bob.accounts, teams], "group_ids": list(group_ids)}
        )
    )
    return w


async def test_a_voice_note_needs_the_voice_permission() -> None:
    bot, inbound = FakeBot(), FakeInbound()
    channel = _channel(bot, gate=_gate(await _bob_on_teams("member")))
    task = await _started(channel, bot, inbound=inbound)
    await _deliver(channel, bot, _voice_note())
    # Bob may chat, so he is told why; nothing was fetched or transcribed.
    assert [t[2] for t in bot.texts] == [NO_VOICE_RIGHT] and not inbound.handled
    task.cancel()


async def test_a_stranger_s_voice_note_is_ignored_without_a_word() -> None:
    bot, inbound = FakeBot(), FakeInbound()
    channel = _channel(bot)
    task = await _started(channel, bot, inbound=inbound)
    await _deliver(channel, bot, _voice_note())
    assert bot.texts == [] and not inbound.handled
    task.cancel()


async def test_with_the_voice_permission_a_voice_note_is_listened_to() -> None:
    w = await _bob_on_teams("member")
    member = w.groups.get("member")
    assert member is not None
    await w.groups.put(
        member.model_copy(update={"permissions": member.permissions | {Permission.VOICE}})
    )
    bot = FakeBot()
    channel = _channel(bot, gate=_gate(w))
    task = await _started(channel, bot)
    await _deliver(channel, bot, _voice_note())
    # Let through: here transcription is not set up, so it says it could not listen.
    assert [t[2] for t in bot.texts] == [NO_VOICE]
    task.cancel()
