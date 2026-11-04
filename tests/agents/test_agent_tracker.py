from aios.agents.agent_tracker import AgentTracker


async def test_a_subagent_is_named_by_its_start_hook() -> None:
    tracker = AgentTracker()
    hook = tracker.hooks()["SubagentStart"][0].hooks[0]
    assert tracker.name_of(None) == "orchestrator"
    assert tracker.name_of("a1") is None
    await hook({"agent_id": "a1", "agent_type": "calendar"}, None, {"signal": None})
    assert tracker.name_of("a1") == "calendar"


def test_the_main_thread_is_the_chosen_agent() -> None:
    assert AgentTracker("calendar").name_of(None) == "calendar"
