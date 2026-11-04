from aios.channels.cli.cli_channel import CliChannel
from aios.conversations.conversation_delivery import ConversationDelivery
from tests.fakes.world import World


async def test_cli_lines_become_messages_in_numbered_conversations() -> None:
    world = await World().setup()
    await world.users.put(
        world.alice.model_copy(update={"accounts": [*world.alice.accounts, CliChannel.ACCOUNT]})
    )
    lines = iter(["hello\n", "/new\n", "again\n", ""])
    output: list[str] = []
    cli = CliChannel(read_line=lambda: next(lines), write=output.append)
    world.channels = world.channels.__class__({"cli": lambda: cli}, ["cli"])
    world.gateway._channels = world.channels  # route replies to the CLI under test
    world.gateway._delivery = ConversationDelivery(world.channels)

    await cli.start(world.gateway, world.approval_service)

    threads = [r.binding.thread for r in world.engine.requests]  # type: ignore[attr-defined]
    assert threads == ["1", "2"]
    assert output.count("\nai-os> ok\n") == 2


async def test_without_a_terminal_the_channel_waits_instead_of_ending_ai_os() -> None:
    import asyncio

    cli = CliChannel(read_line=lambda: "", write=lambda _: None, interactive=False)
    task = asyncio.create_task(cli.start(None, None))  # type: ignore[arg-type]
    await asyncio.sleep(0.05)
    assert not task.done()  # an empty stdin no longer reads as /quit
    task.cancel()
