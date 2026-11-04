from pydantic import BaseModel, Field


class PruneRequest(BaseModel):
    days: int = Field(ge=1)
