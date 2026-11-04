from pydantic import BaseModel


class MergeRequest(BaseModel):
    source: str
    into: str
