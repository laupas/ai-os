from aios.approvals.policy_verdict import PolicyVerdict
from aios.approvals.tool_call import ToolCall
from aios.entities.users.user import User
from tests.agents.agent_world import AgentWorld

USER = User(id="u", name="Alice")


def call(agent: str | None, tool: str, **tool_input: object) -> ToolCall:
    return ToolCall(
        tool_name=tool, tool_input=tool_input, user=USER, conversation_id="c", agent=agent
    )


def denied(w: AgentWorld, c: ToolCall) -> bool:
    decision = w.rule.evaluate(c)
    return decision is not None and decision.verdict is PolicyVerdict.DENY


async def test_an_agent_may_use_only_the_connector_tools_it_was_granted(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    await w.add_gcal()
    assert not denied(w, call("calendar", "mcp__gcal__list-events"))
    assert denied(w, call("calendar", "mcp__gcal__delete-event"))
    assert denied(w, call("calendar", "mcp__aios__send_message"))
    assert denied(w, call("messenger", "mcp__gcal__list-events"))


async def test_a_switched_off_connector_is_refused_to_everyone(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    await w.add_gcal(enabled=False)
    assert denied(w, call("calendar", "mcp__gcal__list-events"))


async def test_a_whole_connector_grant_allows_every_tool_on_it(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    await w.add_gcal()
    await w.update("calendar", connectors={"gcal": None})
    assert not denied(w, call("calendar", "mcp__gcal__delete-event"))


def test_skills_are_granted_by_name(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    assert not denied(w, call("messenger", "Skill", skill="message-style"))
    assert denied(w, call("messenger", "Skill", skill="other"))
    assert denied(w, call("calendar", "Skill", skill="message-style"))


def test_builtin_tools_are_per_agent(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    assert not denied(w, call("orchestrator", "WebSearch"))
    assert denied(w, call("messenger", "WebSearch"))


async def test_only_an_agent_with_task_delegates_and_only_to_enabled_agents(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    assert not denied(w, call("orchestrator", "Task", subagent_type="calendar"))
    assert denied(w, call("orchestrator", "Task", subagent_type="orchestrator"))
    assert denied(w, call("messenger", "Task", subagent_type="calendar"))
    await w.update("calendar", enabled=False)
    assert denied(w, call("orchestrator", "Agent", subagent_type="calendar"))


async def test_an_unnamed_or_disabled_agent_may_do_nothing(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    assert denied(w, call(None, "mcp__aios__ask_human"))
    assert denied(w, call("nobody", "mcp__aios__ask_human"))
    await w.update("calendar", enabled=False)
    await w.add_gcal()
    assert denied(w, call("calendar", "mcp__gcal__list-events"))


def test_a_granted_call_is_left_to_the_rules_after_it(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    assert w.rule.evaluate(call("messenger", "mcp__aios__send_message")) is None
