from datetime import timedelta

from aiohttp import web

from aios.channels.channel_directory import ChannelDirectory
from aios.common.build_version import BuildVersion
from aios.common.clock import Clock
from aios.config.app_config import AppConfig
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.engine.claude_credentials import ClaudeCredentials
from aios.entities.approvals.approval import Approval
from aios.entities.approvals.approval_status import ApprovalStatus
from aios.entities.conversations.conversation import Conversation
from aios.entities.memories.memory import Memory
from aios.entities.triggers.trigger import Trigger
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.logs.log_reader import LogReader
from aios.messaging.sender_directory import SenderDirectory
from aios.storage.collection import Collection
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class HealthRoutes(WebRoutes):
    """`/api/me` for everyone, `/api/health` for those who view logs."""

    def __init__(
        self,
        config: AppConfig,
        channels: ChannelDirectory,
        senders: SenderDirectory,
        conversations: Collection[Conversation],
        approvals: Collection[Approval],
        memories: Collection[Memory],
        triggers: Collection[Trigger],
        users: Collection[User],
        log_reader: LogReader,
        clock: Clock,
        connectors: ConnectorCatalog,
        build: BuildVersion,
        credentials: ClaudeCredentials | None = None,
    ) -> None:
        self._config = config
        self._build = build
        self._credentials = credentials
        self._connectors = connectors
        self._channels = channels
        self._senders = senders
        self._conversations = conversations
        self._approvals = approvals
        self._memories = memories
        self._triggers = triggers
        self._users = users
        self._log_reader = log_reader
        self._clock = clock
        self._started_at = clock.now()

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/me", self._me)
        app.router.add_get("/api/health", self._health)

    async def _me(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        return web.json_response(
            {
                "name": caller.user.name,
                "email": caller.account.address,
                "permissions": sorted(caller.permissions),
                "chat": "web" in self._channels.names(),
                "version": self._build.describe(),
            }
        )

    async def _health(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.VIEW_LOGS)
        now = self._clock.now()
        problems = self._log_reader.read(now - timedelta(hours=24), "WARNING")
        errors = [line for line in problems if " ERROR " in line or " CRITICAL " in line]
        return web.json_response(
            {
                "version": self._build.describe(),
                "started_at": self._started_at.isoformat(),
                "uptime_seconds": int((now - self._started_at).total_seconds()),
                "channels": self._channels.names(),
                "senders": self._senders.names(),
                "mcp_servers": sorted(self._connectors.enabled_names()),
                "triggers": self._config.triggers.enabled,
                "claude": self._credentials.status() if self._credentials else None,
                "counts": {
                    "conversations": len(self._conversations.all()),
                    "pending_approvals": len(
                        self._approvals.filter(lambda a: a.status is ApprovalStatus.PENDING)
                    ),
                    "memories": len(self._memories.all()),
                    "triggers": len(self._triggers.all()),
                    "triggers_enabled": len(self._triggers.filter(lambda s: s.enabled)),
                    "users": len(self._users.all()),
                    "warnings_24h": len(problems) - len(errors),
                    "errors_24h": len(errors),
                },
                "last_problem": problems[-1] if problems else None,
            }
        )
