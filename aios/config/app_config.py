from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from aios.config.agent_config import AgentConfig
from aios.config.approval_config import ApprovalConfig
from aios.config.connector_override import ConnectorOverride
from aios.config.files_config import FilesConfig
from aios.config.owner_config import OwnerConfig
from aios.config.scheduler_config import SchedulerConfig
from aios.config.web_config import WebConfig
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
    connectors: dict[str, ConnectorOverride] = {}
    """What is fixed for a connector, by its name; the console shows it and does
    not let it be changed. E.g. `crypto: {settings: {max_chf_per_day: 300}}`."""
    mcp_servers: dict[str, dict[str, Any]] = {}
    """External MCP servers, in Claude Code's `.mcp.json` shape. Copied into the
    connectors on the first start and not read again; manage them in the console."""
    collection_access: dict[str, AgentAccess] = {}
    """Overrides the agent access of a collection, by collection name."""

    @model_validator(mode="before")
    @classmethod
    def _read_older_files(cls, data: Any) -> Any:
        # Until 2026-11-06 the trading limits were `trading:` here; trading is the
        # code connector `crypto` since, and the limits are its settings. Read as
        # fixed by this file, as they were, so no limit loosens by the move.
        if isinstance(data, dict) and "trading" in data:
            data = dict(data)
            trading = data.pop("trading") or {}
            connectors = dict(data.get("connectors") or {})
            crypto = dict(connectors.get("crypto") or {})
            crypto["settings"] = {**trading, **(crypto.get("settings") or {})}
            connectors["crypto"] = crypto
            data["connectors"] = connectors
        return data
