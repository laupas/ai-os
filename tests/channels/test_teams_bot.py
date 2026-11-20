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
