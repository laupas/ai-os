from pydantic import BaseModel


class FearGreed(BaseModel):
    value: int
    classification: str
