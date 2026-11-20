import asyncio
from typing import Any

from aios.approvals.approval_answer_handler import ApprovalAnswerHandler
from aios.channels.message_chunker import MessageChunker
from aios.channels.teams.teams_cards import TeamsCards
from aios.channels.teams.teams_channel import (
    CANNOT_ANSWER,
    DEFAULT_SERVICE_URL,
    NEW_STARTED,
    TeamsChannel,
)
from aios.channels.teams.teams_emoji import TeamsEmoji
from aios.channels.teams.teams_threads import TeamsThreads
from aios.channels.teams.teams_voice_notes import TeamsVoiceNotes
from aios.conversations.inbound_handler import InboundHandler
from aios.conversations.inbound_message import InboundMessage
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.channel_account import ChannelAccount
from aios.progress.progress_event import ProgressEvent

SERVICE = "https://smba.trafficmanager.net/emea/"


class FakeBot:
    """Stands in for `TeamsBot`: delivers activities and records what is sent."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
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

    async def send_text(self, service_url: str, conversation_id: str, text: str) -> str:
        self.texts.append((service_url, conversation_id, text))
        return f"act{len(self.texts)}"

    async def send_card(self, service_url: str, conversation_id: str, card: dict, summary: str):
        self.cards.append((service_url, conversation_id, card))
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


def _channel(bot: FakeBot) -> TeamsChannel:
    return TeamsChannel(
        tenant_id="tenant",
        bot=bot,  # type: ignore[arg-type]
        threads=TeamsThreads(),
        cards=TeamsCards(),
        emoji=TeamsEmoji(),
        chunker=MessageChunker(size=1000),
        voice_notes=TeamsVoiceNotes(NoTranscriber()),  # type: ignore[arg-type]
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


async def test_a_failing_connection_does_not_end_the_channel() -> None:
    bot = FakeBot(fail=True)
    task = asyncio.create_task(_channel(bot).start(FakeInbound(), FakeAnswers()))
    await asyncio.sleep(0.05)
    assert not task.done()  # ending would stop every other channel
    task.cancel()
