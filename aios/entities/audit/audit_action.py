from enum import StrEnum


class AuditAction(StrEnum):
    CREATED = "created"
    CHANGED = "changed"
    DELETED = "deleted"
    PERFORMED = "performed"
    """Something done rather than stored: a restart, a branch switch, a push."""
