from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from aios.config.agent_config import AgentConfig
from aios.config.approval_config import ApprovalConfig
from aios.config.channel_config import ChannelConfig
from aios.config.connector_override import ConnectorOverride
from aios.config.files_config import FilesConfig
from aios.config.owner_config import OwnerConfig
from aios.config.scheduler_config import SchedulerConfig
from aios.config.web_config import WebConfig
from aios.storage.agent_access import AgentAccess


class AppConfig(BaseModel):
    """Behaviour, from config.yaml on the data volume."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    channels: dict[str, ChannelConfig] = {"web": ChannelConfig()}
    """The channels ai-os uses, by name: `slack`, `web`, `signal`, `mail`. What each
    can do (chat, send) is its own; its tokens and numbers are Variables."""
    timezone: str = "Europe/Zurich"
    """For schedules and dates in prompts: an IANA name such as `Europe/Zurich`."""
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

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, name: str) -> str:
        try:
            ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone {name!r}; e.g. Europe/Zurich") from exc
        return name

    @model_validator(mode="before")
    @classmethod
    def _read_older_files(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = cls._channels_as_one_map(data)
        # Until 2026-11-06 trading was part of ai-os, with its limits as `trading:`
        # here. Refused rather than ignored: ignoring it would drop the limits.
        if isinstance(data, dict) and "trading" in data:
            raise ValueError(
                "trading: is not read any more; trading is a code connector now, and its "
                "limits go under connectors.<its name>.settings"
            )
        return data

    @staticmethod
    def _channels_as_one_map(data: dict[str, Any]) -> dict[str, Any]:
        """Until 2026-11-19, `channels: [slack, web]` and `senders: [signal]` were two
        lists of names; both are still read, as one map of channels that are on.
        A channel written without anything (`slack:`) is on."""
        channels = data.get("channels", ["web"] if "senders" in data else None)
        if channels is None:
            return data
        data = dict(data)
        merged: dict[str, Any] = (
            {name: {} for name in channels}
            if isinstance(channels, list)
            else {k: {} if v is None else v for k, v in dict(channels).items()}
        )
        for name in data.pop("senders", None) or []:
            merged.setdefault(name, {})
        data["channels"] = merged
        return data

    def enabled_channels(self) -> list[str]:
        return [name for name, channel in self.channels.items() if channel.enabled]
