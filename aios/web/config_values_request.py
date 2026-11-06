from typing import Any

from pydantic import BaseModel


class ConfigValuesRequest(BaseModel):
    """aios.yaml as the console's form edited it: what is set, defaults left out."""

    values: dict[str, Any]
