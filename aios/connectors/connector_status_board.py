import json
import logging
import os
from pathlib import Path
from typing import Any

from aios.common.clock import Clock
from aios.connectors.connector_status import ConnectorStatus

log = logging.getLogger(__name__)


class ConnectorStatusBoard:
    """Each connector's state and tools, from the `init` message of the latest turn.

    An external server's tools are only known once it has been started, so this is
    also how the console can offer them one by one. The state is kept in memory and
    fills again with the first turn after a restart; the tool names are also kept in
    `tools_file` (names only, nothing secret), so the console can still offer them
    then.
    """

    def __init__(self, clock: Clock, tools_file: Path | None = None) -> None:
        self._clock = clock
        self._statuses: dict[str, ConnectorStatus] = {}
        self._tools_file = Path(tools_file) if tools_file else None
        self._remembered = self._load()

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
        self._remember({name: sorted(found) for name, found in tools.items()})

    def set(self, name: str, status: str, tools: list[str], error: str | None = None) -> None:
        """What a probe of one connector found."""
        self._statuses[name] = ConnectorStatus(
            name=name, status=status, tools=sorted(tools), error=error, seen_at=self._clock.now()
        )
        if tools:
            self._remember({name: sorted(tools)})

    def get(self, name: str) -> ConnectorStatus | None:
        return self._statuses.get(name)

    def tools_of(self, name: str) -> list[str] | None:
        """Seen since the start, else as last seen before it; None when never seen."""
        status = self._statuses.get(name)
        if status and status.tools:
            return status.tools
        return self._remembered.get(name) or None

    def _load(self) -> dict[str, list[str]]:
        if self._tools_file is None or not self._tools_file.exists():
            return {}
        try:
            data = json.loads(self._tools_file.read_text("utf-8"))
            return {str(k): [str(t) for t in v] for k, v in data.items() if isinstance(v, list)}
        except (OSError, ValueError, AttributeError):
            log.warning("could not read %s; connector tools are learnt again", self._tools_file)
            return {}

    def _remember(self, tools: dict[str, list[str]]) -> None:
        changed = {k: v for k, v in tools.items() if v and self._remembered.get(k) != v}
        if not changed:
            return
        self._remembered.update(changed)
        if self._tools_file is None:
            return
        try:
            self._tools_file.parent.mkdir(parents=True, exist_ok=True)
            partial = self._tools_file.with_suffix(".tmp")
            partial.write_text(json.dumps(self._remembered, indent=2, sort_keys=True), "utf-8")
            os.replace(partial, self._tools_file)
        except OSError:
            log.warning("could not write %s", self._tools_file, exc_info=True)
