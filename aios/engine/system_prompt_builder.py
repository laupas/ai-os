from collections.abc import Callable
from zoneinfo import ZoneInfo

from aios.agents.agent_catalog import AgentCatalog
from aios.common.clock import Clock
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.engine.memory_prompt_section import MemoryPromptSection
from aios.engine.turn_request import TurnRequest


class SystemPromptBuilder:
    """The main agent's prompt from the agent catalog (the orchestrator's, or that of
    the agent the conversation was started with), plus who is talking, where and when,
    the connectors this turn goes without because the user has not signed in to them,
    and what `MemoryPromptSection` takes from the memories."""

    def __init__(
        self,
        agents: AgentCatalog,
        clock: Clock,
        timezone: Callable[[], str],
        memories: MemoryPromptSection,
        connectors: ConnectorCatalog | None = None,
    ) -> None:
        self._connectors = connectors
        self._agents = agents
        self._clock = clock
        self._timezone = timezone
        self._memories = memories

    def build(self, request: TurnRequest) -> str:
        zone = ZoneInfo(self._timezone())
        now = self._clock.now().astimezone(zone)
        lines = [
            self._agents.prompt_of(self._agents.main(request.conversation.agent)),
            "",
            "# This turn",
            f"- You are talking with {request.user.name} (user id {request.user.id}).",
            f"- Channel: {request.binding.channel}, address {request.binding.address}.",
            f"- Local time: {now.strftime('%A %Y-%m-%d %H:%M')} ({zone.key}).",
        ]
        if request.voice:
            lines.append(
                f"- {request.user.name} is speaking, not typing: their message is a "
                "transcript and may contain misheard words. Your reply will be read aloud, "
                "so write it for listening: short, plain sentences, no tables, lists, "
                "headings, links or code. Offer to send details in writing instead."
            )
        unavailable = self._connectors.unavailable_for(request.user) if self._connectors else []
        if unavailable:
            lines.append(
                f"- Not available in this turn, because {request.user.name} has not signed in "
                f"with their own account: {', '.join(unavailable)}. If a request needs one, "
                "say so and ask them to sign in under Connectors in the ai-os web console; "
                "do not try another way."
            )
        lines += self._memories.lines(request.user, request.text)
        return "\n".join(lines) + "\n"
