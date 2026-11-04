from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aios.common.clock import Clock
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.schedules.schedule import Schedule
from aios.entities.users.user import User
from aios.scheduler.schedule_runner import ScheduleRunner
from aios.scheduler.schedule_timing import ScheduleTiming
from aios.scheduler.scheduler_loop import SchedulerLoop
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore


class _FixedClock(Clock):
    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


class _RecordingRunner(ScheduleRunner):
    def __init__(self) -> None:
        self.ran: list[str] = []

    async def run(self, schedule: Schedule) -> None:
        self.ran.append(schedule.name)


def _schedule(**overrides: object) -> Schedule:
    data: dict[str, object] = {
        "id": "s1",
        "name": "brief",
        "prompt": "brief me",
        "cron": ["0 7 * * *"],
        "user_id": "u",
    }
    data.update(overrides)
    return Schedule.model_validate(data)


def test_needs_exactly_one_of_cron_and_once_at() -> None:
    with pytest.raises(ValidationError):
        _schedule(cron=[])
    with pytest.raises(ValidationError):
        _schedule(once_at=datetime(2026, 1, 1, tzinfo=UTC))
    with pytest.raises(ValidationError):
        _schedule(cron=["not cron"])
    with pytest.raises(ValidationError):
        _schedule(cron=[], once_at=datetime(2026, 1, 1))  # no offset


def test_cron_is_local_time_and_takes_the_earliest_rule() -> None:
    timing = ScheduleTiming()
    schedule = _schedule(cron=["0 10 * * *", "0 7 * * *"], timezone="Europe/Zurich")
    after = datetime(2026, 7, 1, 0, 0, tzinfo=UTC)  # 02:00 in Zurich (summer)
    assert timing.next_after(schedule, after) == datetime(2026, 7, 1, 5, 0, tzinfo=UTC)


async def _loop(
    schedule: Schedule, now: datetime
) -> tuple[SchedulerLoop, Collection[Schedule], _RecordingRunner, _FixedClock]:
    schedules: Collection[Schedule] = Collection(
        CollectionDefinition(name="schedules", entity=Schedule), InMemoryDocumentStore()
    )
    await schedules.put(schedule)
    runner, clock = _RecordingRunner(), _FixedClock(now)
    return SchedulerLoop(schedules, ScheduleTiming(), runner, clock, 30), schedules, runner, clock


async def _settle() -> None:
    import asyncio

    await asyncio.sleep(0)


async def test_a_new_cron_schedule_waits_for_its_next_slot() -> None:
    start = datetime(2026, 7, 1, 4, 59, tzinfo=UTC)  # 06:59 Zurich
    loop, schedules, runner, clock = await _loop(_schedule(), start)
    await loop.tick()
    await _settle()
    assert runner.ran == [] and schedules.get("s1").last_fired_at == start  # type: ignore[union-attr]
    clock.current = start + timedelta(minutes=1, seconds=10)
    await loop.tick()
    await _settle()
    assert runner.ran == ["brief"]
    await loop.tick()
    await _settle()
    assert runner.ran == ["brief"]  # not twice for one slot


async def test_a_long_missed_slot_is_skipped_not_replayed() -> None:
    fired = datetime(2026, 7, 1, 5, 0, tzinfo=UTC)
    loop, schedules, runner, clock = await _loop(_schedule(last_fired_at=fired), fired)
    clock.current = fired + timedelta(days=1, hours=3)  # down over the next 07:00
    await loop.tick()
    await _settle()
    assert runner.ran == [] and schedules.get("s1").last_fired_at == clock.current  # type: ignore[union-attr]


async def test_once_fires_and_is_removed() -> None:
    at = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)
    loop, schedules, runner, _ = await _loop(
        _schedule(cron=[], once_at=at), at + timedelta(seconds=5)
    )
    await loop.tick()
    await _settle()
    assert runner.ran == ["brief"] and schedules.get("s1") is None


async def test_disabled_schedules_do_not_fire() -> None:
    at = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)
    loop, _, runner, _ = await _loop(
        _schedule(cron=[], once_at=at, enabled=False), at + timedelta(seconds=5)
    )
    await loop.tick()
    await _settle()
    assert runner.ran == []


async def test_runner_opens_the_run_wherever_the_user_is() -> None:
    from aios.channels.channel_directory import ChannelDirectory
    from aios.channels.thread_starter import ThreadStarter
    from aios.conversations.conversation_delivery import ConversationDelivery
    from tests.fakes.fake_channel import FakeChannel
    from tests.fakes.world import World

    class _StartingChannel(FakeChannel, ThreadStarter):
        async def start_thread(self, address: str, text: str) -> ChannelBinding:
            return ChannelBinding(channel=self.name, address=address, thread="run-1")

    world = await World().setup()
    fake, signal = _StartingChannel("fake"), _StartingChannel("signal")
    unused = _StartingChannel("teams")  # Alice has no account there
    world.channels = ChannelDirectory(
        {"fake": lambda: fake, "signal": lambda: signal, "teams": lambda: unused},
        ["fake", "signal", "teams"],
    )
    world.gateway._channels = world.channels
    world.gateway._delivery = ConversationDelivery(world.channels)
    runner = ScheduleRunner(world.users, world.channels, world.gateway)

    await runner.run(_schedule(user_id="alice", agent="calendar"))

    [request] = world.engine.requests  # type: ignore[attr-defined]
    assert request.user.id == "alice" and request.text == "brief me"
    assert request.conversation.agent == "calendar"  # the run goes straight to it
    assert request.binding == ChannelBinding(channel="fake", address="alice", thread="run-1")
    conversation = world.resolver.find(request.binding)
    assert conversation is not None
    assert {b.channel for b in conversation.bindings} == {"fake", "signal"}
    assert fake.texts() == ["ok"] and signal.texts() == ["ok"]  # the prompt is not mirrored


def test_an_older_schedule_document_is_read_with_its_user() -> None:
    old = Schedule.model_validate(
        {
            "id": "s1",
            "name": "brief",
            "prompt": "brief me",
            "cron": ["0 7 * * *"],
            "channel": "slack",
            "address": "C0B8U91RGMQ",
            "run_as_user_id": "alice",
        }
    )
    assert old.user_id == "alice"
    assert "channel" not in old.model_dump()


async def test_runner_does_nothing_for_a_user_without_chat() -> None:
    from tests.fakes.world import World

    world = await World().setup()
    await world.gateway.start_turn(
        User(id="x", name="X"), [ChannelBinding(channel="fake", address="a", thread="t")], "hi"
    )
    assert world.engine.requests == []  # type: ignore[attr-defined]
