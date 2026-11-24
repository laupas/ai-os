from pydantic import BaseModel, ConfigDict, Field


class RateLimitConfig(BaseModel):
    """How often the console answers before it says "too many requests" (429).
    Counted in memory, per client address before signing in and per user after;
    a restart starts the counts afresh. Applies at once."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    enabled: bool = True
    login_per_minute: int = Field(20, ge=1)
    """Per address: the login page's routes, single sign-on and OAuth returns."""
    hooks_per_minute: int = Field(30, ge=1)
    """Per address: trigger webhooks, which start runs that cost tokens."""
    hook_failures: int = Field(10, ge=1)
    """Per address: wrong or unknown webhook tokens before the address is blocked."""
    hook_block_minutes: int = Field(15, ge=1)
    messages_per_minute: int = Field(20, ge=1)
    """Per user: new messages, conversations, voice notes and trigger runs, the
    requests that cost tokens. A group may allow its members more or fewer
    (`Group.messages_per_minute`); the most generous of a user's groups counts."""
    reads_per_minute: int = Field(600, ge=1)
    """Per user: everything else that only reads."""
    writes_per_minute: int = Field(120, ge=1)
    """Per user: everything else that changes something."""
