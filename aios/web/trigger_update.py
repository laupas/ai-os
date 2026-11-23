from pydantic import BaseModel


class TriggerUpdate(BaseModel):
    enabled: bool
