from pydantic import BaseModel, Field


class BranchCommitRequest(BaseModel):
    """A commit of a branch to undo, or to bring the branch back to."""

    branch: str
    commit: str = Field(pattern=r"^[0-9a-f]{7,40}$")
