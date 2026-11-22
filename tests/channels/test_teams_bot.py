import asyncio

import pytest
from microsoft_teams.api import MessageActivity

from aios.channels.teams.teams_activity_reader import TeamsActivityReader
from aios.channels.teams.teams_bot import CARD, TeamsBot
from aios.channels.teams.teams_threads import TeamsThreads

RAW = {
    "type": "message",
    "id": "1700000000001",
    "channelId": "msteams",
    "serviceUrl": "https://smba.trafficmanager.net/emea/",
    "from": {"id": "29:user", "aadObjectId": "AAAA-1111", "name": "Ada"},
    "recipient": {"id": "28:bot", "name": "ai-os"},
    "conversation": {"id": "a:chat", "conversationType": "personal"},
    "text": "hello",
}


def test_an_sdk_activity_reads_back_as_bot_framework_json() -> None:
    """What `TeamsBot.run` hands on must be what the reader expects."""
    activity = MessageActivity.model_validate(RAW)
    dumped = activity.model_dump(mode="json", by_alias=True, exclude_none=True)
    message = TeamsActivityReader(TeamsThreads(), lambda b: False).read(dumped)
    assert message is not None and message.text == "hello"
    assert message.sender.address == "aaaa-1111"
    assert dumped["serviceUrl"] == RAW["serviceUrl"]


def test_a_card_is_sent_as_an_adaptive_card_attachment() -> None:
    message = TeamsBot._card({"type": "AdaptiveCard", "body": []}, "Working…")
    dumped = message.model_dump(by_alias=True, exclude_none=True)
    assert dumped["summary"] == "Working…"
    assert dumped["attachments"][0]["contentType"] == CARD


def test_the_bot_is_made_in_socket_mode_without_connecting() -> None:
    bot = TeamsBot(app_id="00000000-0000-0000-0000-000000000000", password="x", tenant_id="t")
    assert bot._app.socket_mode is not None


async def test_a_wrong_bot_id_is_explained_in_words(monkeypatch) -> None:
    bot = TeamsBot(app_id="00000000-0000-0000-0000-000000000000", password="x", tenant_id="t")

    async def refused(*args: object, **kwargs: object) -> None:
        raise ValueError("unauthorized_client")

    monkeypatch.setattr(bot._app.token_provider, "get_app_token", refused)
    with pytest.raises(RuntimeError, match="not the Teams app's App ID"):
        await bot.check()


async def test_a_cancelled_run_stops_the_sockets_and_passes_the_cancel_on(monkeypatch) -> None:
    """The SDK's start() swallows a cancel and leaves its sockets open; ai-os must end."""
    bot = TeamsBot(app_id="00000000-0000-0000-0000-000000000000", password="x", tenant_id="t")
    started, stopped = asyncio.Event(), []

    async def start() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            return  # as the SDK does

    async def stop() -> None:
        stopped.append(True)

    async def ready() -> None:
        return None

    monkeypatch.setattr(bot._app, "start", start)
    monkeypatch.setattr(bot._app, "stop", stop)
    monkeypatch.setattr(bot, "_initialize", ready)
    task = asyncio.create_task(bot.run(lambda activity: ready()))
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 1)
    assert stopped == [True]


def test_a_chat_thread_reads_back_with_its_reply_chain() -> None:
    raw = {**RAW, "id": "1700000000005", "channelData": {"replyChain": {"id": "1700000000001"}}}
    dumped = MessageActivity.model_validate(raw).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    message = TeamsActivityReader(TeamsThreads(in_chats=True), lambda b: False).read(dumped)
    assert message is not None and message.binding.thread == "chat-1700000000001"


async def test_a_refused_thread_reply_is_posted_at_the_top(monkeypatch) -> None:
    bot = TeamsBot(app_id="00000000-0000-0000-0000-000000000000", password="x", tenant_id="t")
    sent: list[str] = []

    class Sent:
        id = "1800"

    async def ready() -> None:
        return None

    async def reply(conversation_id, message_id, activity, service_url=None):
        raise RuntimeError("HTTP 400")

    async def send(conversation_id, activity, service_url=None):
        sent.append(conversation_id)
        return Sent()

    monkeypatch.setattr(bot, "_initialize", ready)
    monkeypatch.setattr(bot._app, "reply", reply)
    monkeypatch.setattr(bot._app, "send", send)
    assert await bot.send_text("https://s/", "a:chat", "hi", reply_chain=("19:c", "1700")) == "1800"
    assert sent == ["a:chat"]


def test_a_quote_reads_back_through_the_sdk() -> None:
    quote = {"type": "quotedReply", "quotedReply": {"messageId": "1700000000001"}}
    raw = {**RAW, "id": "1700000000009", "entities": [quote]}
    dumped = MessageActivity.model_validate(raw).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    threads = TeamsThreads()
    started = threads.restart("a:chat", "1700000000000")
    threads.remember("1700000000001", started)
    threads.restart("a:chat", "1800000000000")
    message = TeamsActivityReader(threads, lambda b: False).read(dumped)
    assert message is not None and message.binding == started


async def test_a_refused_quote_is_sent_without_it(monkeypatch) -> None:
    bot = TeamsBot(app_id="00000000-0000-0000-0000-000000000000", password="x", tenant_id="t")
    texts: list[str] = []

    class Sent:
        id = "1800"

    async def ready() -> None:
        return None

    async def send(conversation_id, activity, service_url=None):
        texts.append(activity.text)
        if activity.entities:
            raise RuntimeError("HTTP 400")
        return Sent()

    monkeypatch.setattr(bot, "_initialize", ready)
    monkeypatch.setattr(bot._app, "send", send)
    assert await bot.send_text("https://s/", "a:chat", "hi", quote="1700") == "1800"
    assert texts == ['<quoted messageId="1700"/> hi', "hi"]
