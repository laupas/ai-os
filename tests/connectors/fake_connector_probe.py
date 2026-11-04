from aios.connectors.connector_probe import ConnectorProbe
from aios.connectors.connector_status_board import ConnectorStatusBoard
from aios.connectors.probe_result import ProbeResult


class FakeConnectorProbe(ConnectorProbe):
    """Answers with a set result per connector, as the real probe records it."""

    def __init__(self, board: ConnectorStatusBoard) -> None:
        self._board = board
        self.results: dict[str, ProbeResult] = {}

    async def probe(self, name: str) -> ProbeResult:
        result = self.results.get(name, ProbeResult(status="connected", tools=["a", "b"]))
        self._board.set(name, result.status, result.tools, result.error)
        return result
