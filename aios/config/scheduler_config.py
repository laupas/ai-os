from pydantic import BaseModel, ConfigDict


class SchedulerConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    enabled: bool = True
    tick_seconds: float = 30
