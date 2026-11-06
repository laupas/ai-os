from abc import ABC, abstractmethod

from aios.connectors.probe_result import ProbeResult
from aios.entities.users.user import User


class ConnectorProbe(ABC):
    """Starts one connector the way a turn of `user` would, to see whether it comes up."""

    @abstractmethod
    async def probe(self, name: str, user: User | None = None) -> ProbeResult: ...
