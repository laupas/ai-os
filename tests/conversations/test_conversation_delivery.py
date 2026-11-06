from datetime import UTC, datetime

from aios.channels.authored_sender import AuthoredSender
from aios.channels.channel_directory import ChannelDirectory
from aios.conversations.conversation_delivery import ConversationDelivery
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.conversation import Conversation
from aios.entities.users.user import User
from tests.fakes.fake_channel import FakeChannel

SLACK = ChannelBinding(channel="slack", address="C1", thread="1")
WEB = ChannelBinding(channel="web", address="p@example.com", thread="c1")
GONE = ChannelBinding(channel="gone", address="local", thread="1")
ALICE = User(id="alice", name="Alice")


class _AuthoredChannel(FakeChannel, AuthoredSender):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.authored: list[tuple[str, str, str]] = []

    async def send_as(self, binding: ChannelBinding, text: str, author: User, via: str) -> None:
        self.authored.append((text, author.name, via))


def _conversation(*bindings: ChannelBinding) -> Conversation:
    now = datetime.now(UTC)
    return Conversation(id="c1", bindings=list(bindings), created_at=now, updated_at=now)


def _setup(slack: FakeChannel) -> tuple[ConversationDelivery, FakeChannel]:
    web = FakeChannel("web")
    channels = ChannelDirectory({"slack": lambda: slack, "web": lambda: web}, ["slack", "web"])
    return ConversationDelivery(channels), web


async def test_a_reply_goes_to_every_place_and_skips_a_disabled_channel() -> None:
    slack = FakeChannel("slack")
    delivery, web = _setup(slack)

    await delivery.send(_conversation(SLACK, WEB, GONE), "hi")

    assert slack.sent == [(SLACK, "hi")]
    assert web.sent == [(WEB, "hi")]


async def test_a_message_is_mirrored_everywhere_but_where_it_was_written() -> None:
    slack = FakeChannel("slack")
    delivery, web = _setup(slack)

    await delivery.mirror(_conversation(SLACK, WEB), WEB, ALICE, "wohnort?")

    assert slack.sent == [(SLACK, "*Alice (web):* wohnort?")]
    assert web.sent == []


async def test_a_channel_that_can_show_authors_gets_the_author() -> None:
    slack = _AuthoredChannel("slack")
    delivery, _ = _setup(slack)

    await delivery.mirror(_conversation(SLACK, WEB), WEB, ALICE, "wohnort?")

    assert slack.authored == [("wohnort?", "Alice", "web")]
    assert slack.sent == []
