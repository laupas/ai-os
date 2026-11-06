from zoneinfo import ZoneInfo

from aios.agents.agent_catalog import AgentCatalog
from aios.common.clock import Clock
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.engine.turn_request import TurnRequest
from aios.entities.memories.memory import Memory
from aios.entities.memories.memory_kind import MemoryKind
from aios.storage.collection import Collection


class SystemPromptBuilder:
    """The main agent's prompt from the agent catalog (the orchestrator's, or that of
    the agent the conversation was started with), plus who is talking, where and when,
    the remembered preferences shared by every user and the user's own, and the
    connectors this turn goes without because the user has not signed in to them."""

    def __init__(
        self,
        agents: AgentCatalog,
        clock: Clock,
        timezone: str,
        memories: Collection[Memory],
        connectors: ConnectorCatalog | None = None,
    ) -> None:
        self._connectors = connectors
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
        unavailable = self._connectors.unavailable_for(request.user) if self._connectors else []
        if unavailable:
            lines.append(
                f"- Not available in this turn, because {request.user.name} has not signed in "
                f"with their own account: {', '.join(unavailable)}. If a request needs one, "
                "say so and ask them to sign in under Connectors in the ai-os web console; "
                "do not try another way."
            )
        preferences = self._memories.filter(lambda m: m.kind is MemoryKind.PREFERENCE)
        shared = [m for m in preferences if m.user_id is None]
        own = [m for m in preferences if m.user_id == request.user.id]
        if shared or own:
            lines += [
                "",
                "# Remembered preferences",
                "Apply each one only where it fits: a mail signoff belongs in mails, never "
                "in your chat replies.",
            ]
        if shared:
            lines += ["", "## Shared by every user"] + [self._line(m) for m in shared]
        if own:
            lines += ["", f"## {request.user.name}'s own"] + [self._line(m) for m in own]
        return "\n".join(lines) + "\n"

    @staticmethod
    def _line(memory: Memory) -> str:
        return f"- {memory.subject + ': ' if memory.subject else ''}{memory.text}"
