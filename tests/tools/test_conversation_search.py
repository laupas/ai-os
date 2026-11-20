from datetime import timedelta

import pytest

from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.conversation import Conversation
from aios.entities.conversations.message_role import MessageRole
from aios.entities.users.user import User
from aios.tools.conversation_search_tool import ConversationSearchTool
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError
from tests.fakes.world import World


def _context(user: User, conversation_id: str = "now") -> ToolContext:
    return ToolContext(
        conversation_id=conversation_id,
        user=user,
        binding=ChannelBinding(channel="fake", address=user.id, thread="t"),
    )


async def _conversation(world: World, cid: str, participants: list[str], *texts: str) -> None:
    now = world.clock.now()
    await world.conversations.put(
        Conversation(id=cid, participants=participants, created_at=now, updated_at=now)
    )
    for text in texts:
        await world.recorder.record(cid, MessageRole.USER, text, "fake", participants[0])


async def _world() -> tuple[World, ConversationSearchTool]:
    world = await World().setup()
    await _conversation(world, "a1", ["alice"], "The heating in Matten is broken")
    await _conversation(world, "b1", ["bob"], "Bob's secret: the heating code is 1234")
    await _conversation(world, "ab", ["alice", "bob"], "Heating appointment on Friday")
    await _conversation(world, "now", ["alice"], "What did I say about the heating?")
    return world, ConversationSearchTool(world.conversations, world.recorder, world.clock)


async def test_finds_only_the_users_own_conversations() -> None:
    world, tool = await _world()
    result = await tool.run({"query": "HEATING"}, _context(world.alice))
    assert "Matten" in result and "Friday" in result
    assert "1234" not in result
    result = await tool.run({"query": "heating"}, _context(world.bob))
    assert "1234" in result and "Friday" in result and "Matten" not in result


async def test_another_users_conversation_cannot_be_named() -> None:
    world, tool = await _world()
    with pytest.raises(ToolError, match="No earlier conversation"):
        await tool.run({"conversation_id": "b1"}, _context(world.alice))
    result = await tool.run({"conversation_id": "a1"}, _context(world.alice))
    assert "Matten" in result


async def test_leaves_out_the_current_conversation_and_activity() -> None:
    world, tool = await _world()
    await world.recorder.record("a1", MessageRole.ACTIVITY, "used heating tool", "fake")
    result = await tool.run({"query": "heating"}, _context(world.alice, "now"))
    assert "What did I say" not in result and "used heating tool" not in result


async def test_all_words_must_match_and_days_limit() -> None:
    world, tool = await _world()
    assert "Matten" not in await tool.run({"query": "heating friday"}, _context(world.alice))
    world.clock._now += timedelta(days=10)
    await world.recorder.record("a1", MessageRole.ASSISTANT, "Heating fixed", "fake")
    result = await tool.run({"query": "heating", "days": 2}, _context(world.alice))
    assert "Heating fixed" in result and "broken" not in result


async def test_needs_a_query_or_a_conversation() -> None:
    world, tool = await _world()
    with pytest.raises(ToolError):
        await tool.run({}, _context(world.alice))
