from datetime import timedelta

from aios.bootstrap.startup_notice import TEXT, StartupNotice
from aios.channels.channel_directory import ChannelDirectory
from aios.channels.thread_starter import ThreadStarter
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.channel_account import ChannelAccount
from tests.fakes.fake_channel import FakeChannel
from tests.fakes.world import World


class _StartingChannel(FakeChannel, ThreadStarter):
    def __init__(self, name: str = "fake", fail: bool = False) -> None:
        super().__init__(name)
        self.threads: list[tuple[str, str]] = []
        self._fail = fail

    async def start_thread(self, address: str, text: str) -> ChannelBinding:
        if self._fail:
            raise RuntimeError("slack is down")
        self.threads.append((address, text))
        return ChannelBinding(channel=self.name, address=address, thread="1")


async def _notice(world: World, channels: ChannelDirectory, tmp_path) -> StartupNotice:
    return StartupNotice(world.users, channels, world.clock, tmp_path / "startup_notice")


async def test_tells_the_owner_on_a_channel_that_can_start_threads(tmp_path) -> None:
    world = await World().setup()
    channel = _StartingChannel()
    channels = ChannelDirectory({"fake": lambda: channel}, ["fake"])

    await (await _notice(world, channels, tmp_path)).run()

    assert channel.threads == [("alice", TEXT)]


async def test_says_nothing_on_a_channel_that_cannot_start_threads(tmp_path) -> None:
    world = await World().setup()

    await (await _notice(world, world.channels, tmp_path)).run()

    assert world.channel.sent == []


async def test_skips_an_owner_without_an_account_on_the_channel(tmp_path) -> None:
    world = await World().setup()
    await world.users.put(
        world.alice.model_copy(
            update={"accounts": [ChannelAccount(channel="signal", address="+41000000001")]}
        )
    )
    channel = _StartingChannel()
    channels = ChannelDirectory({"fake": lambda: channel}, ["fake"])

    await (await _notice(world, channels, tmp_path)).run()

    assert channel.threads == []


async def test_a_restart_soon_after_says_nothing(tmp_path) -> None:
    world = await World().setup()
    channel = _StartingChannel()
    channels = ChannelDirectory({"fake": lambda: channel}, ["fake"])

    await (await _notice(world, channels, tmp_path)).run()
    await (await _notice(world, channels, tmp_path)).run()

    assert len(channel.threads) == 1


async def test_a_restart_after_the_quiet_period_tells_again(tmp_path) -> None:
    world = await World().setup()
    channel = _StartingChannel()
    channels = ChannelDirectory({"fake": lambda: channel}, ["fake"])
    marker = tmp_path / "startup_notice"

    await StartupNotice(world.users, channels, world.clock, marker, timedelta(seconds=1)).run()
    await StartupNotice(world.users, channels, world.clock, marker, timedelta(seconds=1)).run()

    assert len(channel.threads) == 2


async def test_a_failing_channel_does_not_raise(tmp_path) -> None:
    world = await World().setup()
    channel = _StartingChannel(fail=True)
    channels = ChannelDirectory({"fake": lambda: channel}, ["fake"])

    await (await _notice(world, channels, tmp_path)).run()
