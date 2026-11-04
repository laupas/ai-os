from enum import StrEnum


class PolicyVerdict(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"
