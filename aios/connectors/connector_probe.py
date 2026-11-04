from abc import ABC, abstractmethod

from aios.connectors.probe_result import ProbeResult


class ConnectorProbe(ABC):
    """Starts one connector the way a turn would, to see whether it comes up."""

    @abstractmethod
    async def probe(self, name: str) -> ProbeResult: ...
