from pydantic import BaseModel


class DeleteBranchRequest(BaseModel):
    branch: str
    force: bool = False
    """Delete even with changes that are on no other branch."""
