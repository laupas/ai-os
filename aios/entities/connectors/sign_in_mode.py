from enum import StrEnum


class SignInMode(StrEnum):
    """Whose account a connector's OAuth sign-in is."""

    SHARED = "shared"
    """One account for everybody, signed in by an administrator."""

    PER_USER = "per_user"
    """Each user signs in with their own account and uses only that one."""
