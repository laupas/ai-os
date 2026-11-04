from pydantic import BaseModel


class BranchRequest(BaseModel):
    """A new branch, from `start` (the running branch when left out)."""

    name: str
    start: str | None = None
