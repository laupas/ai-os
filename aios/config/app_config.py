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
    not let it be changed. E.g. `trading: {settings: {max_chf_per_day: 300}}`."""
    mcp_servers: dict[str, dict[str, Any]] = {}
    """External MCP servers, in Claude Code's `.mcp.json` shape. Copied into the
    connectors on the first start and not read again; manage them in the console."""
    collection_access: dict[str, AgentAccess] = {}
    """Overrides the agent access of a collection, by collection name."""

    @model_validator(mode="before")
    @classmethod
    def _read_older_files(cls, data: Any) -> Any:
        # Until 2026-11-06 trading was part of ai-os, with its limits as `trading:`
        # here. Refused rather than ignored: ignoring it would drop the limits.
        if isinstance(data, dict) and "trading" in data:
            raise ValueError(
                "trading: is not read any more; trading is a code connector now, and its "
                "limits go under connectors.<its name>.settings"
            )
        return data
