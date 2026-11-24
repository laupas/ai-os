from enum import StrEnum


class Permission(StrEnum):
    """What a group can grant. The only list of rights that lives in code."""

    CHAT = "chat"
    """May talk to ai-os on a channel, the web console included, and keep their own
    memories there."""

    APPROVE = "approve"
    """May answer approval requests."""

    RECEIVE_UNAPPROVED = "receive_unapproved"
    """May be sent a message without asking for approval first."""

    MANAGE_AGENTS = "manage_agents"
    """May create, change and delete agents other than the fixed ones, granting only
    connectors available to them and only to their own groups or everyone."""

    MANAGE_SKILLS = "manage_skills"
    """May create, change and delete skills."""

    MANAGE_CONNECTORS = "manage_connectors"
    """May add, change and delete connectors and sign in their shared accounts. A
    connector can run a program on the server and reads secrets, so this is as good
    as administering."""

    MANAGE_VARIABLES = "manage_variables"
    """May set variables and secrets (never read a secret back)."""

    MANAGE_TRIGGERS = "manage_triggers"
    """May create and change triggers that run for themselves."""

    MANAGE_SHARED_MEMORIES = "manage_shared_memories"
    """May write memories shared with every user."""

    VIEW_LOGS = "view_logs"
    """May read the logs, the audit trail and the health page."""

    MANAGE_USERS = "manage_users"
    """May approve changes to users and groups."""

    ADMINISTER = "administer"
    """Everything in the console: the rights above that manage something, every
    user's triggers, memories and conversations, settings, store and restart."""

    @property
    def description(self) -> str:
        """What the right means, for the console's group editor."""
        return {
            Permission.CHAT: "May talk to ai-os on a channel and in the web console.",
            Permission.APPROVE: "May answer approval requests.",
            Permission.RECEIVE_UNAPPROVED: (
                "May be sent a message without asking for approval first."
            ),
            Permission.MANAGE_AGENTS: (
                "May create and change agents (not the fixed ones), with the connectors "
                "available to them, for their own groups or everyone."
            ),
            Permission.MANAGE_SKILLS: "May create and change skills.",
            Permission.MANAGE_CONNECTORS: (
                "May add and change connectors. A connector runs programs and reads "
                "secrets: as good as administer."
            ),
            Permission.MANAGE_VARIABLES: "May set variables and secrets (never read one back).",
            Permission.MANAGE_TRIGGERS: "May create and change their own triggers.",
            Permission.MANAGE_SHARED_MEMORIES: "May write memories shared with every user.",
            Permission.VIEW_LOGS: "May read logs, the audit trail and health.",
            Permission.MANAGE_USERS: "May approve an agent's changes to users and groups.",
            Permission.ADMINISTER: (
                "Everything: all of the managing rights, every user's triggers, memories "
                "and conversations, settings, store, restart."
            ),
        }[self]

    @property
    def implied(self) -> frozenset["Permission"]:
        """The rights that come with this one: administer brings every managing right."""
        if self is Permission.ADMINISTER:
            return frozenset(
                {
                    Permission.MANAGE_AGENTS,
                    Permission.MANAGE_SKILLS,
                    Permission.MANAGE_CONNECTORS,
                    Permission.MANAGE_VARIABLES,
                    Permission.MANAGE_TRIGGERS,
                    Permission.MANAGE_SHARED_MEMORIES,
                    Permission.VIEW_LOGS,
                }
            )
        return frozenset()

    @property
    def powerful(self) -> bool:
        """Whether whoever holds it controls ai-os, so that a group with it is never
        filled automatically (new users, a sign-in provider's groups)."""
        return self in {
            Permission.ADMINISTER,
            Permission.MANAGE_USERS,
            Permission.MANAGE_CONNECTORS,
        }
