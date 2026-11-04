from enum import StrEnum


class Permission(StrEnum):
    """What a role can grant. The only list of rights that lives in code."""

    CHAT = "chat"
    """May talk to ai-os on a channel."""

    APPROVE = "approve"
    """May answer approval requests."""

    RECEIVE_UNAPPROVED = "receive_unapproved"
    """May be sent a message without asking for approval first."""

    MANAGE_USERS = "manage_users"
    """May approve changes to users and roles."""

    ADMINISTER = "administer"
    """May use the web console's controls: health, logs, every conversation,
    schedules, memories, settings and restart."""

    @property
    def description(self) -> str:
        """What the right means, for the console's role editor."""
        return {
            Permission.CHAT: "May talk to ai-os on a channel.",
            Permission.APPROVE: "May answer approval requests.",
            Permission.RECEIVE_UNAPPROVED: (
                "May be sent a message without asking for approval first."
            ),
            Permission.MANAGE_USERS: "May approve an agent's changes to users and roles.",
            Permission.ADMINISTER: (
                "May use the web console's controls: settings, agents, connectors, "
                "logs, every conversation, restart."
            ),
        }[self]
