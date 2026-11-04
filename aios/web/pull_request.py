from pydantic import BaseModel


class PullRequest(BaseModel):
    branch: str
