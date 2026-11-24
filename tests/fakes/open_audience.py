from aios.entities.users.user import User
from aios.users.audience import Audience


class OpenAudience(Audience):
    """Everyone is in every audience: for tests about something else."""

    def includes(self, user: User | None, available_to: list[str] | None) -> bool:
        return True
