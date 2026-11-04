from enum import StrEnum


class AgentAccess(StrEnum):
    """How far agents may reach into a collection through the data tools."""

    NONE = "none"
    READ = "read"
    WRITE = "write"

    def allows_read(self) -> bool:
        return self in (AgentAccess.READ, AgentAccess.WRITE)

    def allows_write(self) -> bool:
        return self is AgentAccess.WRITE
