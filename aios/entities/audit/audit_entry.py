from datetime import datetime

from pydantic import BaseModel

from aios.entities.audit.audit_action import AuditAction


class AuditEntry(BaseModel):
    """One change to ai-os's settings: who, when, what. Appended to the audit log,
    never rewritten.

    Configuration in the git repository is not appended here: its history is the
    record, and `ConfigHistory` reads it into the same shape. `fields` names what
    changed; `detail` shows old and new values only where
    they are known not to be secret (see `AuditPolicy.show_values`).
    """

    at: datetime
    actor: str
    actor_email: str
    area: str
    """A collection (`users`, `connectors`, ...), `aios.yaml`, `git` or `ai-os`."""
    item: str
    action: AuditAction
    fields: list[str] = []
    detail: str | None = None
    commit: str | None = None
    """Set for a change read from the configuration repository's history."""
