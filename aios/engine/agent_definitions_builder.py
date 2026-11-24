from claude_agent_sdk import AgentDefinition

from aios.agents.agent_catalog import AgentCatalog
from aios.agents.agent_grant_rule import DELEGATE_TOOLS
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.connectors.connector_status_board import ConnectorStatusBoard
from aios.entities.agents.agent import Agent
from aios.entities.users.user import User
from aios.users.audience import Audience


class AgentDefinitionsBuilder:
    """The subagents of a turn, as SDK definitions, from the agent catalog.

    Their `tools` decide what each subagent *sees*; `AgentGrantRule` decides what it
    may *do*. A connector granted whole whose tools are not known yet (it has not
    been started since ai-os did) leaves `tools` unset, so the subagent sees every
    tool and the rule refuses the ones it was not granted.

    Only the agents available to the turn's user are offered, and only with the
    connectors available to them.
    """

    def __init__(
        self,
        agents: AgentCatalog,
        connectors: ConnectorCatalog,
        board: ConnectorStatusBoard,
        audience: Audience,
    ) -> None:
        self._agents = agents
        self._connectors = connectors
        self._board = board
        self._audience = audience

    def delegates_for(self, user: User) -> list[Agent]:
        return [
            a for a in self._agents.delegates() if self._audience.includes(user, a.available_to)
        ]

    def build(self, user: User) -> dict[str, AgentDefinition]:
        return {
            spec.name: AgentDefinition(
                description=spec.description,
                prompt=self._agents.prompt_of(spec),
                tools=self._tools(spec, user),
                skills=spec.skills or None,
                model=spec.model,
            )
            for spec in self.delegates_for(user)
        }

    def skills(self, main: Agent, delegating: bool, user: User) -> list[str]:
        """Every skill the turn's agents may use: the session loads only these."""
        specs = [main, *(self.delegates_for(user) if delegating else [])]
        return sorted({skill for spec in specs for skill in spec.skills})

    @staticmethod
    def delegates_work(spec: Agent) -> bool:
        return any(t in spec.builtin_tools for t in DELEGATE_TOOLS)

    def _tools(self, spec: Agent, user: User) -> list[str] | None:
        tools = [t for t in spec.builtin_tools if t not in DELEGATE_TOOLS]
        if spec.skills:
            tools.append("Skill")
        for server, granted in spec.connectors.items():
            if not self._connectors.is_enabled(server):
                continue
            if server != ConnectorCatalog.BUILTIN and not self._connectors.available_to(
                server, user, self._audience
            ):
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
