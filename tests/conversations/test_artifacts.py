import pytest

from aios.channels.channel_directory import ChannelDirectory
from aios.channels.web.web_channel import WebChannel
from aios.conversations.artifact_publisher import ArtifactPublisher
from aios.conversations.artifact_store import ArtifactStore
from aios.conversations.conversation_deleter import ConversationDeleter
from aios.conversations.turn_canceller import TurnCanceller
from aios.entities.artifacts.artifact_format import ArtifactFormat
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.message_role import MessageRole
from aios.tools.create_artifact_tool import CreateArtifactTool
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError
from tests.fakes.fake_channel import FakeChannel
from tests.fakes.world import World

FAKE = ChannelBinding(channel="fake", address="room", thread="t")
WEB = ChannelBinding(channel="web", address="alice@example.com", thread="w")
PAGE = "<!doctype html><title>Run</title><h1>Done</h1>"


async def _setup(
    public_url: str | None = "https://aios.example/",
) -> tuple[World, ArtifactStore, ArtifactPublisher]:
    world = await World().setup()
    world.channels = ChannelDirectory(
        {"fake": lambda: world.channel, "web": lambda: WebChannel(world.ids)}, ["fake", "web"]
    )
    conversation = await world.resolver.resolve(FAKE, world.alice)
    await world.resolver.attach(conversation, WEB)
    store = ArtifactStore(world.store)
    publisher = ArtifactPublisher(
        store,
        world.recorder,
        world.conversations,
        world.channels,
        world.clock,
        world.ids,
        public_url,
    )
    return world, store, publisher


async def _conversation_id(world: World) -> str:
    return world.conversations.all()[0].id


async def test_an_artifact_is_kept_recorded_and_linked_where_no_file_can_go() -> None:
    world, store, publisher = await _setup()
    cid = await _conversation_id(world)
    artifact = await publisher.publish(
        cid, world.alice, FAKE, "Run report", ArtifactFormat.HTML, PAGE
    )

    kept = await store.get(artifact.id)
    assert kept is not None and kept.content == PAGE and kept.conversation_id == cid
    [message] = await world.recorder.history(cid)
    assert message.role is MessageRole.ARTIFACT and message.text == "Run report"
    assert message.artifact is not None and message.artifact.id == artifact.id
    # The web binding shows the recorded message; only the fake channel gets text.
    [text] = world.channel.texts()
    assert "Run report" in text and f"https://aios.example/#/chat/{cid}" in text


async def test_without_a_public_url_the_link_names_the_console() -> None:
    world, _, publisher = await _setup(public_url=None)
    cid = await _conversation_id(world)
    await publisher.publish(cid, world.alice, FAKE, "Notes", ArtifactFormat.MARKDOWN, "# Hi")
    assert "web console" in world.channel.texts()[0]


async def test_one_failing_place_does_not_stop_the_artifact() -> None:
    world, store, publisher = await _setup()

    class Broken(FakeChannel):
        async def send(self, binding: ChannelBinding, text: str) -> None:
            raise RuntimeError("down")

    world.channel = Broken()
    cid = await _conversation_id(world)
    artifact = await publisher.publish(cid, world.alice, FAKE, "R", ArtifactFormat.HTML, PAGE)
    assert await store.get(artifact.id) is not None


async def test_deleting_the_conversation_deletes_its_artifacts() -> None:
    world, store, publisher = await _setup()
    cid = await _conversation_id(world)
    artifact = await publisher.publish(cid, world.alice, FAKE, "R", ArtifactFormat.HTML, PAGE)
    await ConversationDeleter(world.conversations, world.recorder, TurnCanceller(), store).delete(
        cid
    )
    assert await store.get(artifact.id) is None


async def test_an_id_that_is_no_storage_name_is_simply_not_found() -> None:
    _, store, _ = await _setup()
    assert await store.get("../users/alice") is None


async def test_the_tool_publishes_into_the_turns_conversation() -> None:
    world, store, publisher = await _setup()
    cid = await _conversation_id(world)
    context = ToolContext(conversation_id=cid, user=world.alice, binding=FAKE)
    result = await CreateArtifactTool(publisher).run(
        {"title": "Weekly", "format": "markdown", "content": "# Week"}, context
    )
    assert "Weekly" in result
    [message] = await world.recorder.history(cid)
    assert message.artifact is not None and message.artifact.format is ArtifactFormat.MARKDOWN


@pytest.mark.parametrize(
    "args",
    [
        {"title": "", "format": "html", "content": PAGE},
        {"title": "x" * 201, "format": "html", "content": PAGE},
        {"title": "R", "format": "pdf", "content": PAGE},
        {"title": "R", "format": "html", "content": "  "},
    ],
)
async def test_the_tool_refuses_bad_input(args: dict[str, str]) -> None:
    world, _, publisher = await _setup()
    context = ToolContext(
        conversation_id=await _conversation_id(world), user=world.alice, binding=FAKE
    )
    with pytest.raises(ToolError):
        await CreateArtifactTool(publisher).run(args, context)
