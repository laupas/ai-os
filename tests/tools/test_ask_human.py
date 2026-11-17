import asyncio

from aios.entities.conversations.channel_binding import ChannelBinding
from aios.tools.ask_human_tool import AskHumanTool
from aios.tools.tool_context import ToolContext
from tests.fakes.world import World


async def test_an_agents_question_may_be_answered_by_voice() -> None:
    world = await World().setup()
    binding = ChannelBinding(channel="fake", address="alice", thread="t")
    context = ToolContext(conversation_id="c1", user=world.alice, binding=binding)
    asking = asyncio.create_task(
        AskHumanTool(world.approval_service).run(
            {"question": "Carol?", "options": ["Carol", "Dave"]}, context
        )
    )
    await asyncio.sleep(0.01)

    [approval] = world.approvals.all()
    assert approval.voice_answerable
    await world.approval_service.answer(approval.id, "Carol", world.alice.accounts[0])
    assert await asking == "The user answered: Carol"
