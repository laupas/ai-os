from pydantic import BaseModel, ConfigDict


class TriggersConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    enabled: bool = True
    """Off, no trigger runs, neither on time nor by webhook; they can still be
    started by hand in the console."""
    tick_seconds: float = 30
    """How often due triggers are looked for. A trigger runs at most this late."""
