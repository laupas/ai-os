from typing import Any

from pydantic import BaseModel


class SectionRequest(BaseModel):
    """One top-level section of aios.yaml as the console sends it; None removes it,
    so all of it is back to the defaults."""

    value: Any = None
