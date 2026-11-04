from zoneinfo import ZoneInfo

from aios.agents.agent_catalog import AgentCatalog
from aios.common.clock import Clock
from aios.engine.turn_request import TurnRequest
from aios.entities.memories.memory import Memory
from aios.entities.memories.memory_kind import MemoryKind
from aios.storage.collection import Collection


class SystemPromptBuilder:
    """The main agent's prompt from the agent catalog (the orchestrator's, or that of
    the agent the conversation was started with), plus who is talking, where and when,
    and the user's remembered preferences."""

    def __init__(
        self, agents: AgentCatalog, clock: Clock, timezone: str, memories: Collection[Memory]
    ) -> None:
        self._agents = agents
        self._clock = clock
        self._zone = ZoneInfo(timezone)
        self._memories = memories

    def build(self, request: TurnRequest) -> str:
        now = self._clock.now().astimezone(self._zone)
        lines = [
            self._agents.prompt_of(self._agents.main(request.conversation.agent)),
            "",
            "# This turn",
            f"- You are talking with {request.user.name} (user id {request.user.id}).",
            f"- Channel: {request.binding.channel}, address {request.binding.address}.",
            f"- Local time: {now.strftime('%A %Y-%m-%d %H:%M')} ({self._zone.key}).",
        ]
        preferences = self._memories.filter(lambda m: m.kind is MemoryKind.PREFERENCE)
        if preferences:
            lines += [
                "",
                "# Remembered preferences",
                "Apply each one only where it fits: a mail signoff belongs in mails, never "
                "in your chat replies.",
            ]
            lines += [f"- {m.subject + ': ' if m.subject else ''}{m.text}" for m in preferences]
        return "\n".join(lines) + "\n"
