from datetime import UTC, datetime

from aios.channels.slack.markdown_to_mrkdwn import MarkdownToMrkdwn
from aios.channels.slack.message_chunker import MessageChunker
from aios.channels.slack.slack_blocks import SlackBlocks
from aios.channels.slack.slack_event_reader import SlackEventReader
from aios.entities.approvals.approval import Approval
from aios.entities.conversations.channel_binding import ChannelBinding

BOT = "UBOT"


def _reader(known: set[str] | None = None) -> SlackEventReader:
    return SlackEventReader(BOT, lambda b: b.thread in (known or set()))


def _event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "type": "message",
        "user": "U1",
        "channel": "C1",
        "channel_type": "channel",
        "ts": "100.1",
        "text": "hello",
    }
    event.update(overrides)
    return event


def test_dm_is_always_read_and_starts_its_own_thread() -> None:
    message = _reader().read(_event(channel_type="im"))
    assert message is not None
    assert message.binding == ChannelBinding(channel="slack", address="C1", thread="100.1")
    assert message.sender.address == "U1"


def test_channel_message_needs_a_mention_and_loses_it() -> None:
    assert _reader().read(_event()) is None
    message = _reader().read(_event(text=f"<@{BOT}> what's up"))
    assert message is not None and message.text == "what's up"


def test_reply_in_a_known_thread_needs_no_mention() -> None:
    message = _reader({"99.0"}).read(_event(thread_ts="99.0"))
    assert message is not None and message.binding.thread == "99.0"


def test_bots_edits_and_empty_mentions_are_ignored() -> None:
    reader = _reader()
    assert reader.read(_event(channel_type="im", bot_id="B1")) is None
    assert reader.read(_event(channel_type="im", subtype="message_changed")) is None
    assert reader.read(_event(text=f"<@{BOT}>")) is None


def test_markdown_becomes_mrkdwn_but_code_is_untouched() -> None:
    converter = MarkdownToMrkdwn()
    text = "## Title\n**bold** and [site](https://x.ch)\n```\n**not bold**\n```"
    assert converter.convert(text) == (
        "*Title*\n*bold* and <https://x.ch|site>\n```\n**not bold**\n```"
    )


def test_tables_become_code_blocks() -> None:
    result = MarkdownToMrkdwn().convert("| a | bb |\n|---|---|\n| 1 | 2 |")
    assert result == "```\na  bb\n-  --\n1  2\n```"


def test_chunker_prefers_line_breaks() -> None:
    chunker = MessageChunker(size=10)
    assert chunker.split("aaaa\nbbbb\ncccc") == ["aaaa\nbbbb", "cccc"]
    assert chunker.split("x" * 25) == ["x" * 10, "x" * 10, "x" * 5]
    assert chunker.split("") == [""]


def test_approval_buttons_carry_id_and_answer() -> None:
    approval = Approval(
        id="a1",
        conversation_id="c",
        binding=ChannelBinding(channel="slack", address="C1", thread="1.0"),
        question="Send?",
        options=["Yes", "No"],
        created_at=datetime.now(UTC),
    )
    blocks = SlackBlocks()
    buttons = blocks.approval(approval)[1]["elements"]
    assert [blocks.read_approval_value(b["value"]) for b in buttons] == [
        ("a1", "Yes"),
        ("a1", "No"),
    ]


def test_binding_of_a_threaded_message_is_its_thread() -> None:
    binding = SlackBlocks.binding_of("C1", {"ts": "2.0", "thread_ts": "1.0"})
    assert binding.thread == "1.0"


def test_voice_note_without_text_is_kept_with_its_file() -> None:
    event = _event(
        channel_type="im",
        text="",
        subtype="file_share",
        files=[{"name": "audio_message.m4a", "mimetype": "audio/mp4", "url_private_download": "u"}],
    )
    message = _reader().read(event)
    assert message is not None and message.text == ""
    assert message.attachments[0].mime_type == "audio/mp4"


def test_voice_notes_recognises_audio() -> None:
    from aios.channels.slack.slack_voice_notes import SlackVoiceNotes
    from aios.transcription.whisper_transcriber import WhisperTranscriber

    notes = SlackVoiceNotes("xoxb", WhisperTranscriber(None, None))
    message = _reader().read(
        _event(channel_type="im", text="", files=[{"name": "a.ogg", "mimetype": ""}])
    )
    assert message is not None and notes.audio_in(message) is not None
