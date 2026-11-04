import asyncio

from aios.entities.approvals.approval_status import ApprovalStatus
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.channel_account import ChannelAccount
from tests.fakes.world import World

BINDING = ChannelBinding(channel="fake", address="room", thread="t1")
ALICE = ChannelAccount(channel="fake", address="alice")
BOB = ChannelAccount(channel="fake", address="bob")


async def _pending_request(world: World) -> asyncio.Task[str | None]:
    task = asyncio.create_task(
        world.approval_service.request("c1", BINDING, "Send it?", ["Yes", "No"])
    )
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    return task


async def test_question_is_shown_as_text_on_a_channel_without_buttons() -> None:
    world = await World().setup()
    task = await _pending_request(world)
    assert world.channel.texts() == ["Send it?\nReply with: Yes / No"]
    task.cancel()


async def test_approver_answer_resolves_the_request() -> None:
    world = await World().setup()
    task = await _pending_request(world)
    [approval] = world.approvals.all()
    assert await world.approval_service.answer(approval.id, "yes", ALICE)
    assert await task == "Yes"
    stored = world.approvals.get(approval.id)
    assert stored is not None and stored.status is ApprovalStatus.ANSWERED
    assert stored.answered_by == "alice"


async def test_user_without_approve_permission_cannot_answer() -> None:
    world = await World().setup()
    task = await _pending_request(world)
    [approval] = world.approvals.all()
    assert not await world.approval_service.answer(approval.id, "Yes", BOB)
    assert not task.done()
    task.cancel()


async def test_answer_must_be_one_of_the_options() -> None:
    world = await World().setup()
    task = await _pending_request(world)
    [approval] = world.approvals.all()
    assert not await world.approval_service.answer(approval.id, "maybe", ALICE)
    task.cancel()


async def test_typed_reply_in_the_same_conversation_answers() -> None:
    world = await World().setup()
    task = await _pending_request(world)
    assert not await world.approval_service.answer_from_text("c2", ALICE, "No")
    assert await world.approval_service.answer_from_text("c1", ALICE, " no ")
    assert await task == "No"


async def test_no_answer_in_time_is_none_and_expires() -> None:
    world = await World(timeout_seconds=0.05).setup()
    assert await world.approval_service.request("c1", BINDING, "?", ["Yes", "No"]) is None
    [approval] = world.approvals.all()
    assert approval.status is ApprovalStatus.EXPIRED


async def test_pending_approvals_expire_at_startup() -> None:
    world = await World().setup()
    task = await _pending_request(world)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await world.approval_service.expire_pending()
    assert all(a.status is ApprovalStatus.EXPIRED for a in world.approvals.all())


async def test_the_question_is_shown_wherever_the_conversation_is() -> None:
    from datetime import UTC, datetime

    from aios.approvals.approval_service import ApprovalService
    from aios.channels.channel_directory import ChannelDirectory
    from aios.conversations.conversation_event import ConversationEvent
    from aios.conversations.conversation_observer import ConversationObserver
    from aios.entities.conversations.conversation import Conversation
    from tests.fakes.fake_channel import FakeChannel

    class _Seen(ConversationObserver):
        def __init__(self) -> None:
            self.events: list[ConversationEvent] = []

        def notify(self, event: ConversationEvent) -> None:
            self.events.append(event)

    world = await World().setup()
    other = FakeChannel("other")
    elsewhere = ChannelBinding(channel="other", address="x", thread="9")
    now = datetime.now(UTC)
    await world.conversations.put(
        Conversation(id="c1", bindings=[BINDING, elsewhere], created_at=now, updated_at=now)
    )
    seen = _Seen()
    service = ApprovalService(
        world.approvals,
        world.users,
        world.authorizer,
        ChannelDirectory(
            {"fake": lambda: world.channel, "other": lambda: other}, ["fake", "other"]
        ),
        world.clock,
        world.ids,
        5,
        world.conversations,
        [seen],
    )

    task = asyncio.create_task(service.request("c1", BINDING, "Send it?", ["Yes", "No"]))
    await asyncio.sleep(0.01)

    assert world.channel.texts() == ["Send it?\nReply with: Yes / No"]
    assert other.sent == [(elsewhere, "Send it?\nReply with: Yes / No")]
    assert [e.kind for e in seen.events] == ["approval"]
    task.cancel()
