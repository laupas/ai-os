from typing import Any

from pydantic import BaseModel, ConfigDict


class ConnectorOverride(BaseModel):
    """What aios.yaml used to fix for one connector; `ConnectorSettingsMigration`
    moves it onto the connector."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    settings: dict[str, Any] = {}
    """Settings of a code connector, over what is set on the connector."""
