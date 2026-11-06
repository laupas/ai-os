import asyncio
import logging
import time
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, PermissionResultDeny

from aios.connectors.connector_catalog import ConnectorCatalog
from aios.connectors.connector_probe import ConnectorProbe
from aios.connectors.connector_status_board import ConnectorStatusBoard
from aios.connectors.probe_result import ProbeResult
from aios.entities.users.user import User

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 120  # an npx server downloads itself on its first start


class ClaudeConnectorProbe(ConnectorProbe):
    """Starts one connector through the same CLI a turn uses, with the same
    variables and sign-in filled in, and asks for its status. No message is sent,
    so no model is called; the CLI only connects the server and lists its tools.

    "connected" means the server started and answered; it does not prove that
    every tool works (a server can start fine and fail on its first real call).
    """

    def __init__(
        self, connectors: ConnectorCatalog, board: ConnectorStatusBoard, repo_dir: Path
    ) -> None:
        self._connectors = connectors
        self._board = board
        self._repo_dir = Path(repo_dir)

    async def probe(self, name: str, user: User | None = None) -> ProbeResult:
        config = self._connectors.server_config(name, user)
        if config is None:
            raise ValueError(f"no connector called {name}")
        started = time.monotonic()

        async def refuse(*_: object) -> PermissionResultDeny:
            return PermissionResultDeny(message="a probe runs no tools")

        options = ClaudeAgentOptions(
            cwd=str(self._repo_dir),
            setting_sources=[],
            tools=[],
            allowed_tools=[],
            mcp_servers={name: config},  # type: ignore[dict-item]
            strict_mcp_config=True,
            can_use_tool=refuse,
            permission_mode="default",
        )
        entry: dict = {"status": "pending"}
        try:
            async with asyncio.timeout(TIMEOUT_SECONDS):
                async with ClaudeSDKClient(options=options) as client:
                    while entry.get("status") == "pending":
                        status = await client.get_mcp_status()
                        entry = next(
                            (dict(s) for s in status["mcpServers"] if s["name"] == name),
                            {"status": "failed", "error": "the CLI did not report the server"},
                        )
                        if entry.get("status") == "pending":
                            await asyncio.sleep(1)
        except TimeoutError:
            entry = {"status": "failed", "error": f"no answer within {TIMEOUT_SECONDS} seconds"}
        except Exception as exc:
            log.exception("probing connector %s failed", name)
            entry = {"status": "failed", "error": str(exc)}
        info = entry.get("serverInfo") or {}
        result = ProbeResult(
            status=entry.get("status", "failed"),
            error=entry.get("error"),
            server=f"{info['name']} {info.get('version', '')}".strip()
            if info.get("name")
            else None,
            tools=sorted(t["name"] for t in entry.get("tools") or []),
            seconds=round(time.monotonic() - started, 1),
        )
        self._board.set(name, result.status, result.tools, result.error)
        return result
