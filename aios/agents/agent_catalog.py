import re

from aios.agents.agent_unavailable_error import AgentUnavailableError
from aios.agents.catalog_error import CatalogError
from aios.entities.agents.agent import Agent
from aios.storage.collection import Collection

NAME = re.compile(r"^[a-z][a-z0-9-]{0,40}$")
AGENTS_PLACEHOLDER = "{{agents}}"


class AgentCatalog:
    """Every agent. The orchestrator is the main thread of a turn unless the
    conversation was started with another agent; the others are what it may
    delegate to. Fixed agents are features of ai-os (schedules, memories, messages,
    configuration),
    so they can be edited but never disabled or deleted. The configurator is the
    only agent that may change agents, skills and connectors.
    """

    ORCHESTRATOR = "orchestrator"
    CONFIGURATOR = "ai-os-configurator"
    FIXED = frozenset({ORCHESTRATOR, CONFIGURATOR, "scheduler", "memory", "messenger"})

    def __init__(self, agents: Collection[Agent]) -> None:
        self._agents = agents

    def all(self) -> list[Agent]:
        return sorted(self._agents.all(), key=lambda a: (a.id != self.ORCHESTRATOR, a.id))

    def get(self, name: str) -> Agent | None:
        agent = self._agents.get(name)
        if agent is not None and name in self.FIXED and not agent.enabled:
            return agent.model_copy(update={"enabled": True})  # written behind our back
        return agent

    def is_fixed(self, name: str) -> bool:
        return name in self.FIXED

    def orchestrator(self) -> Agent:
        agent = self.get(self.ORCHESTRATOR)
        if agent is None:
            raise RuntimeError("there is no orchestrator agent")
        return agent

    def main(self, name: str | None) -> Agent:
        """The agent that runs a turn's main thread: the orchestrator, or the one a
        conversation was started with."""
        if name is None or name == self.ORCHESTRATOR:
            return self.orchestrator()
        agent = self.get(name)
        if agent is None:
            raise AgentUnavailableError(f"the agent {name} does not exist any more")
        if not agent.enabled:
            raise AgentUnavailableError(f"the agent {name} is switched off")
        return agent

    def delegates(self) -> list[Agent]:
        """The enabled agents the orchestrator may hand work to."""
        return [a for a in self.all() if a.enabled and a.id != self.ORCHESTRATOR]

    def prompt_of(self, agent: Agent) -> str:
        """The agent's prompt, with `{{agents}}` replaced by the enabled agents (name
        and description), so a prompt can name them without going stale."""
        if AGENTS_PLACEHOLDER not in agent.prompt:
            return agent.prompt
        listing = "\n".join(f"- `{a.id}`: {a.description}" for a in self.delegates())
        return agent.prompt.replace(AGENTS_PLACEHOLDER, listing)

    async def save(self, agent: Agent) -> Agent:
        if not NAME.match(agent.id):
            raise CatalogError("a name is lower-case letters, digits and dashes")
        if agent.id in self.FIXED and not agent.enabled:
            raise CatalogError(f"{agent.id} is fixed and cannot be switched off")
        if not agent.description.strip() or not agent.prompt.strip():
            raise CatalogError("an agent needs a description and a prompt")
        return await self._agents.put(agent)

    async def delete(self, name: str) -> None:
        if name in self.FIXED:
            raise CatalogError(f"{name} is fixed and cannot be deleted")
        await self._agents.delete(name)
