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
