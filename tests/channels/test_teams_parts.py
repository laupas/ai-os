from datetime import UTC, datetime

from aios.channels.teams.teams_activity_reader import FILE, TeamsActivityReader
from aios.channels.teams.teams_cards import TeamsCards
from aios.channels.teams.teams_channel_type import TeamsChannelType
from aios.channels.teams.teams_emoji import TeamsEmoji
from aios.channels.teams.teams_threads import TeamsThreads
from aios.entities.approvals.approval import Approval
from aios.entities.conversations.channel_binding import ChannelBinding

BOT = "28:bot-app-id"
USER = "AAAA-1111"


def _reader(known: set[str] | None = None, threads: TeamsThreads | None = None):
    return TeamsActivityReader(threads or TeamsThreads(), lambda b: b.thread in (known or set()))


def _activity(**overrides: object) -> dict[str, object]:
    activity: dict[str, object] = {
        "type": "message",
        "id": "1700000000001",
        "serviceUrl": "https://smba.trafficmanager.net/emea/",
        "from": {"id": "29:user", "aadObjectId": USER, "name": "Ada"},
        "recipient": {"id": BOT, "name": "ai-os"},
        "conversation": {"id": "a:personal-chat", "conversationType": "personal"},
        "text": "hello",
    }
    activity.update(overrides)
    return activity


def _channel_post(text: str, mention: bool) -> dict[str, object]:
    entities = (
        [{"type": "mention", "mentioned": {"id": BOT, "name": "ai-os"}, "text": "<at>ai-os</at>"}]
        if mention
        else []
    )
    return _activity(
        conversation={
            "id": "19:abc@thread.tacv2;messageid=1699999999999",
            "conversationType": "channel",
        },
        text=text,
        entities=entities,
    )


def test_personal_chat_is_always_read_as_one_conversation() -> None:
    message = _reader().read(_activity())
    assert message is not None
    assert message.binding == ChannelBinding(
        channel="teams", address="a:personal-chat", thread="chat"
    )
    assert message.sender.address == USER.lower()
    assert message.text == "hello"


def test_channel_post_needs_a_mention_and_loses_it() -> None:
    assert _reader().read(_channel_post("<at>ai-os</at> hi", mention=False)) is None
    message = _reader().read(_channel_post("<at>ai-os</at> what&#39;s up", mention=True))
    assert message is not None and message.text == "what's up"
    assert message.binding == ChannelBinding(
        channel="teams", address="19:abc@thread.tacv2", thread="1699999999999"
    )


def test_reply_in_a_known_thread_needs_no_mention() -> None:
    message = _reader({"1699999999999"}).read(_channel_post("more", mention=False))
    assert message is not None and message.text == "more"


def test_button_presses_and_senders_without_entra_id_are_not_messages() -> None:
    reader = _reader()
    assert reader.read(_activity(value={"aios": "stop"})) is None
    assert reader.read(_activity(**{"from": {"id": "29:x"}})) is None
    assert reader.read(_activity(type="conversationUpdate")) is None


def test_files_become_attachments() -> None:
    file = {
        "contentType": FILE,
        "name": "note.m4a",
        "content": {"downloadUrl": "https://dl/x", "fileType": "m4a"},
    }
    message = _reader().read(_activity(text="", attachments=[file]))
    assert message is not None
    assert message.attachments[0].name == "note.m4a"
    assert message.attachments[0].url == "https://dl/x"


def test_a_new_chat_thread_is_used_until_the_next_one() -> None:
    threads = TeamsThreads()
    restarted = threads.restart("a:personal-chat", "42")
    message = _reader(threads=threads).read(_activity())
    assert message is not None and message.binding == restarted
    assert TeamsThreads.conversation_id(restarted) == "a:personal-chat"
    channel = ChannelBinding(channel="teams", address="19:abc@thread.tacv2", thread="17")
    assert TeamsThreads.conversation_id(channel) == "19:abc@thread.tacv2;messageid=17"


def test_cards_carry_their_answers_and_read_back() -> None:
    cards = TeamsCards()
    approval = Approval(
        id="ap1",
        conversation_id="c1",
        binding=ChannelBinding(channel="teams", address="a", thread="chat"),
        question="Send it?",
        options=["Yes", "No"],
        created_at=datetime.now(UTC),
    )
    actions = cards.approval(approval)["actions"]
    assert [a["title"] for a in actions] == ["Yes", "No"]
    data = cards.read_action(actions[1]["data"])
    assert data is not None and data["approval_id"] == "ap1" and data["answer"] == "No"
    assert cards.read_action({"other": 1}) is None
    assert cards.read_action(cards.status(["· x"], running=True)["actions"][0]["data"])
    assert cards.status(["· x"], running=False)["actions"] == []


def test_slack_shortcodes_become_emoji() -> None:
    assert TeamsEmoji().convert(":alarm_clock: daily :nope:") == "⏰ daily :nope:"


def test_the_setup_steps_link_to_the_developer_portal() -> None:
    steps = TeamsChannelType(transcriber=None).setup  # type: ignore[arg-type]
    assert steps[0].link == "https://dev.teams.microsoft.com"
    assert any("Socket mode" in step.text for step in steps)
