from pydantic import BaseModel


class StoreSourceRequest(BaseModel):
    url: str
    branch: str | None = None
