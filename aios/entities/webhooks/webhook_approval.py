from enum import StrEnum


class WebhookApproval(StrEnum):
    """Whether a post to a webhook destination needs a human's yes first."""

    ASK = "ask"
    """Every post is asked for."""
    ALLOW = "allow"
    """Posted without asking: the destination is trusted by being configured."""
    DENY = "deny"
    """Never posted by an agent; the console's test still works."""
