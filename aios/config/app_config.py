from typing import Any

from pydantic import BaseModel, ConfigDict

from aios.config.agent_config import AgentConfig
from aios.config.approval_config import ApprovalConfig
from aios.config.files_config import FilesConfig
from aios.config.owner_config import OwnerConfig
from aios.config.scheduler_config import SchedulerConfig
from aios.config.web_config import WebConfig
from aios.crypto.trade_limits import TradeLimits
from aios.storage.agent_access import AgentAccess


class AppConfig(BaseModel):
    """Behaviour, from config.yaml on the data volume."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    channels: list[str] = ["web"]
    senders: list[str] = []
    timezone: str = "Europe/Zurich"
    owner: OwnerConfig | None = None
    approval: ApprovalConfig = ApprovalConfig()
    agent: AgentConfig = AgentConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    files: FilesConfig = FilesConfig()
    web: WebConfig = WebConfig()
    trading: TradeLimits = TradeLimits()
    mcp_servers: dict[str, dict[str, Any]] = {}
    """External MCP servers, in Claude Code's `.mcp.json` shape. Copied into the
    connectors on the first start and not read again; manage them in the console."""
    collection_access: dict[str, AgentAccess] = {}
    """Overrides the agent access of a collection, by collection name."""
