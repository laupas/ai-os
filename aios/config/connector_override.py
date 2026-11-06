from typing import Any

from pydantic import BaseModel, ConfigDict


class ConnectorOverride(BaseModel):
    """What aios.yaml fixes for one connector. The console shows these values and
    does not let them be changed, and no agent can change this file."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    settings: dict[str, Any] = {}
    """Settings of a code connector, over what is set on the connector."""
