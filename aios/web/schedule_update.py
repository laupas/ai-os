from pydantic import BaseModel


class ScheduleUpdate(BaseModel):
    enabled: bool
