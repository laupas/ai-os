from pydantic import BaseModel, ConfigDict


class AuditPolicy(BaseModel):
    """How changes to one collection are recorded."""

    model_config = ConfigDict(frozen=True)

    ignored_fields: frozenset[str] = frozenset()
    """Fields that change by themselves (a token renewal, a schedule firing); a put
    that changes only these is not a settings change and is not recorded."""
    show_values: bool = False
    """Record old and new values, not only the field names. Only for collections
    that never hold a secret."""
