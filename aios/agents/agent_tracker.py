from typing import Any

from claude_agent_sdk import HookContext, HookMatcher

from aios.agents.agent_catalog import AgentCatalog


class AgentTracker:
    """Which agent a tool call comes from, for one turn.

    `can_use_tool` is told only a subagent's id; the `SubagentStart` hook reports the
    id together with the agent's name, before that subagent can call anything. A call
    without an id is the main thread's: the orchestrator, or the agent the
    conversation was started with. An id never announced has no name, and the grant
    rule refuses it.
    """

    def __init__(self, main: str = AgentCatalog.ORCHESTRATOR) -> None:
        self._main = main
        self._names: dict[str, str] = {}

    def hooks(self) -> dict[str, list[HookMatcher]]:
        return {"SubagentStart": [HookMatcher(hooks=[self._started])]}

    def name_of(self, agent_id: str | None) -> str | None:
        if agent_id is None:
            return self._main
        return self._names.get(agent_id)

    async def _started(
        self, data: Any, _tool_use_id: str | None, _context: HookContext
    ) -> dict[str, Any]:
        agent_id, agent_type = data.get("agent_id"), data.get("agent_type")
        if agent_id and agent_type:
            self._names[agent_id] = agent_type
        return {}
