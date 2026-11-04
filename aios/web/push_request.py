from pydantic import BaseModel


class PushRequest(BaseModel):
    """One branch, or every branch when left out."""

    branch: str | None = None
