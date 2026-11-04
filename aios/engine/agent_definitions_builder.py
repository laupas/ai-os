from claude_agent_sdk import AgentDefinition

from aios.agents.agent_catalog import AgentCatalog
from aios.agents.agent_grant_rule import DELEGATE_TOOLS
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.connectors.connector_status_board import ConnectorStatusBoard
from aios.entities.agents.agent import Agent


class AgentDefinitionsBuilder:
    """The subagents of a turn, as SDK definitions, from the agent catalog.

    Their `tools` decide what each subagent *sees*; `AgentGrantRule` decides what it
    may *do*. A connector granted whole whose tools are not known yet (it has not
    been started since ai-os did) leaves `tools` unset, so the subagent sees every
    tool and the rule refuses the ones it was not granted.
    """

    def __init__(
        self, agents: AgentCatalog, connectors: ConnectorCatalog, board: ConnectorStatusBoard
    ) -> None:
        self._agents = agents
        self._connectors = connectors
        self._board = board

    def build(self) -> dict[str, AgentDefinition]:
        return {
            spec.name: AgentDefinition(
                description=spec.description,
                prompt=self._agents.prompt_of(spec),
                tools=self._tools(spec),
                skills=spec.skills or None,
                model=spec.model,
            )
            for spec in self._agents.delegates()
        }

    def skills(self, main: Agent, delegating: bool) -> list[str]:
        """Every skill the turn's agents may use: the session loads only these."""
        specs = [main, *(self._agents.delegates() if delegating else [])]
        return sorted({skill for spec in specs for skill in spec.skills})

    @staticmethod
    def delegates_work(spec: Agent) -> bool:
        return any(t in spec.builtin_tools for t in DELEGATE_TOOLS)

    def _tools(self, spec: Agent) -> list[str] | None:
        tools = [t for t in spec.builtin_tools if t not in DELEGATE_TOOLS]
        if spec.skills:
            tools.append("Skill")
        for server, granted in spec.connectors.items():
            if not self._connectors.is_enabled(server):
                continue
            names = granted if granted is not None else self._known_tools(server)
            if names is None:
                return None
            tools += [f"mcp__{server}__{name}" for name in names]
        return tools

    def _known_tools(self, server: str) -> list[str] | None:
        if server == ConnectorCatalog.BUILTIN:
            return self._connectors.builtin_tools()
        return self._board.tools_of(server)
