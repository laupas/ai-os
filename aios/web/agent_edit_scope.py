from aios.agents.agent_catalog import AgentCatalog
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.entities.agents.agent import Agent
from aios.entities.users.audience_entry import EVERYONE
from aios.entities.users.group import Group
from aios.entities.users.permission import Permission
from aios.storage.collection import Collection
from aios.users.audience import Audience
from aios.web.web_caller import WebCaller


class AgentEditScope:
    """What somebody with `manage_agents` but not `administer` may do to an agent,
    so that the right cannot be turned into more access than they have.

    They leave the fixed agents alone, add no built-in tool (the file tools reach
    the server's files) and no tool of ai-os's own connector, grant only connectors
    that are available to them, and make an agent available only to their own
    groups or everyone. What an administrator granted before stays as it is: only
    what a save adds is checked. Administrators may do anything."""

    def __init__(
        self,
        agents: AgentCatalog,
        connectors: ConnectorCatalog,
        groups: Collection[Group],
        audience: Audience,
    ) -> None:
        self._agents = agents
        self._connectors = connectors
        self._groups = groups
        self._audience = audience

    def connectors(self, caller: WebCaller) -> set[str] | None:
        """The connectors the caller may grant; None: every one, ai-os's own included."""
        if caller.can(Permission.ADMINISTER):
            return None
        return {
            c.id
            for c in self._connectors.all()
            if c.enabled and self._audience.includes(caller.user, c.available_to)
        }

    def groups(self, caller: WebCaller) -> list[Group]:
        """The groups the caller may make an agent available to."""
        groups = sorted(self._groups.all(), key=lambda g: g.name.casefold())
        if caller.can(Permission.ADMINISTER):
            return groups
        return [g for g in groups if g.id in caller.user.group_ids]

    def refusal(self, caller: WebCaller, current: Agent | None, wanted: Agent) -> str | None:
        """Why the caller may not turn `current` (None: a new agent) into `wanted`."""
        if caller.can(Permission.ADMINISTER):
            return None
        if self._agents.is_fixed(wanted.id):
            return f"{wanted.id} is a fixed agent; only an administrator changes it"
        before = current or Agent(id=wanted.id, description="", prompt="")
        added_tools = set(wanted.builtin_tools) - set(before.builtin_tools)
        if added_tools:
            return f"only an administrator grants built-in tools: {', '.join(sorted(added_tools))}"
        reach = self.connectors(caller) or set()
        changed = [
            name
            for name, tools in wanted.connectors.items()
            if before.connectors.get(name, ...) != tools and name not in reach
        ]
        if changed:
            return f"not available to you, so not yours to grant: {', '.join(sorted(changed))}"
        own = {EVERYONE, *(f"group:{g}" for g in caller.user.group_ids)}
        added = set(wanted.available_to or []) - set(before.available_to or []) - own
        if added:
            return f"available only to your own groups, not: {', '.join(sorted(added))}"
        return None
