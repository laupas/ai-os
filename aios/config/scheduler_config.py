from pydantic import BaseModel


class SchedulerConfig(BaseModel):
    enabled: bool = True
    tick_seconds: float = 30
