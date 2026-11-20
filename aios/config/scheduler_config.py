from pydantic import BaseModel, ConfigDict


class SchedulerConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    enabled: bool = True
    """Off, no schedule runs; they can still be started by hand in the console."""
    tick_seconds: float = 30
    """How often due schedules are looked for. A schedule runs at most this late."""
