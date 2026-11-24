from abc import ABC, abstractmethod

from aios.entities.users.user import User


class Audience(ABC):
    """Whether a user is among those an agent or connector is available to."""

    @abstractmethod
    def includes(self, user: User | None, available_to: list[str] | None) -> bool: ...
