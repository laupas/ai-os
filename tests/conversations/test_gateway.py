import asyncio

from aios.conversations.gateway import NOT_ALLOWED, STOPPED
from aios.conversations.inbound_message import InboundMessage
from aios.engine.turn_request import TurnRequest
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.message_role import MessageRole
from aios.entities.users.channel_account import ChannelAccount
from aios.progress.progress_event import ProgressEvent
from tests.fakes.fake_engine import FakeEngine
from tests.fakes.world import World

BINDING = ChannelBinding(channel="fake", address="room", thread="t1")


def _message(sender: str, text: str = "hi") -> InboundMessage:
    return InboundMessage(
        binding=BINDING, sender=ChannelAccount(channel="fake", address=sender), text=text
    )


async def test_unknown_sender_is_refused_and_nothing_runs() -> None:
    world = await World().setup()
    await world.gateway.handle(_message("stranger"))
    assert world.channel.texts() == [NOT_ALLOWED]
    assert world.engine.requests == []  # type: ignore[attr-defined]


async def test_user_without_chat_permission_is_refused() -> None:
    world = await World().setup()
    await world.gateway.handle(_message("bob"))
    assert world.channel.texts() == [NOT_ALLOWED]


async def test_turn_replies_records_history_and_keeps_the_session() -> None:
    world = await World(engine=FakeEngine(reply="hello", session_id="s-42")).setup()
    await world.gateway.handle(_message("alice", "hi"))

    assert world.channel.texts() == ["hello"]
    conversation = world.resolver.find(BINDING)
    assert conversation is not None and conversation.agent_session_id == "s-42"
    history = await world.recorder.history(conversation.id)
    assert [(m.role, m.text) for m in history] == [
        (MessageRole.USER, "hi"),
        (MessageRole.ASSISTANT, "hello"),
    ]


async def test_the_steps_of_a_turn_are_recorded_before_the_reply() -> None:
    steps = [
        ProgressEvent(label="Asking the second-brain agent", tool_name="Task"),
        ProgressEvent(label="Asking the second-brain agent", tool_name="Task"),
        ProgressEvent(label="Looking through notes", tool_name="Grep"),
    ]
    world = await World(engine=FakeEngine(reply="hello", progress=steps)).setup()
    await world.gateway.handle(_message("alice", "hi"))

    conversation = world.resolver.find(BINDING)
    assert conversation is not None
    history = await world.recorder.history(conversation.id)
    assert [(m.role, m.text) for m in history] == [
        (MessageRole.USER, "hi"),
        (MessageRole.ACTIVITY, "Asking the second-brain agent\nLooking through notes"),
        (MessageRole.ASSISTANT, "hello"),
    ]


async def test_next_turn_resumes_the_stored_session() -> None:
    engine = FakeEngine(session_id="s-1")
    world = await World(engine=engine).setup()
    await world.gateway.handle(_message("alice"))
    await world.gateway.handle(_message("alice"))
    assert [r.conversation.agent_session_id for r in engine.requests] == [None, "s-1"]


async def test_engine_failure_is_reported_not_raised() -> None:
    async def fail(_: TurnRequest) -> None:
        raise RuntimeError("no network")

    world = await World(engine=FakeEngine(behaviour=fail)).setup()
    await world.gateway.handle(_message("alice"))
    assert world.channel.texts() == ["Something went wrong: no network"]


async def test_a_typed_yes_answers_a_waiting_approval_instead_of_starting_a_turn() -> None:
    answers: list[str | None] = []

    async def ask(request: TurnRequest) -> None:
        answers.append(
            await world.approval_service.request(
                request.conversation.id, request.binding, "Go?", ["Yes", "No"]
            )
        )

    engine = FakeEngine(behaviour=ask)
    world = await World(engine=engine).setup()
    turn = asyncio.create_task(world.gateway.handle(_message("alice", "do it")))
    await asyncio.sleep(0.01)
    await world.gateway.handle(_message("alice", "yes"))
    await turn
    assert answers == ["Yes"] and len(engine.requests) == 1


async def test_stop_cancels_the_running_turn() -> None:
    async def hang(_: TurnRequest) -> None:
        await asyncio.sleep(60)

    world = await World(engine=FakeEngine(behaviour=hang)).setup()
    turn = asyncio.create_task(world.gateway.handle(_message("alice")))
    await asyncio.sleep(0.01)
    assert await world.gateway.cancel(BINDING, ChannelAccount(channel="fake", address="alice"))
    await turn
    assert world.channel.texts() == [STOPPED]
