from typing import Any

from aios.common.clock import Clock
from aios.connectors.connector_status import ConnectorStatus


class ConnectorStatusBoard:
    """Each connector's state and tools, from the `init` message of the latest turn.

    An external server's tools are only known once it has been started, so this is
    also how the console can offer them one by one. Kept in memory: after a restart
    it fills again with the first turn.
    """

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._statuses: dict[str, ConnectorStatus] = {}

    def record(self, init: dict[str, Any]) -> None:
        tools: dict[str, list[str]] = {}
        for name in init.get("tools") or []:
            if isinstance(name, str) and name.startswith("mcp__"):
                server, _, tool = name[5:].partition("__")
                tools.setdefault(server, []).append(tool)
        now = self._clock.now()
        for server in init.get("mcp_servers") or []:
            name = server.get("name") if isinstance(server, dict) else None
            if name:
                self._statuses[name] = ConnectorStatus(
                    name=name,
                    status=server.get("status"),
                    tools=sorted(tools.get(name, [])),
                    seen_at=now,
                )

    def set(self, name: str, status: str, tools: list[str], error: str | None = None) -> None:
        """What a probe of one connector found."""
        self._statuses[name] = ConnectorStatus(
            name=name, status=status, tools=sorted(tools), error=error, seen_at=self._clock.now()
        )

    def get(self, name: str) -> ConnectorStatus | None:
        return self._statuses.get(name)

    def tools_of(self, name: str) -> list[str] | None:
        status = self._statuses.get(name)
        return status.tools if status and status.tools else None
