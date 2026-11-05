import asyncio

import pytest

from aios.engine.turn_deadline import TurnDeadline


async def test_the_turn_is_stopped_when_its_time_is_used_up() -> None:
    deadline = TurnDeadline(0.05)
    with pytest.raises(TimeoutError):
        async with deadline.running():
            await asyncio.sleep(1)


async def test_waiting_for_a_human_does_not_count() -> None:
    deadline = TurnDeadline(0.1)
    async with deadline.running():
        await asyncio.sleep(0.05)
        async with deadline.waiting():
            await asyncio.sleep(0.2)  # longer than the whole turn may take
        await asyncio.sleep(0.03)  # still within what was left


async def test_the_clock_runs_again_after_the_wait() -> None:
    deadline = TurnDeadline(0.1)
    with pytest.raises(TimeoutError):
        async with deadline.running():
            async with deadline.waiting():
                await asyncio.sleep(0.15)
            await asyncio.sleep(0.2)


async def test_parallel_waits_stop_the_clock_until_the_last_one_ends() -> None:
    deadline = TurnDeadline(0.1)

    async def wait(seconds: float) -> None:
        async with deadline.waiting():
            await asyncio.sleep(seconds)

    async with deadline.running():
        await asyncio.gather(wait(0.15), wait(0.25))


async def test_waiting_outside_a_turn_does_nothing() -> None:
    async with TurnDeadline(0.01).waiting():
        await asyncio.sleep(0.02)
