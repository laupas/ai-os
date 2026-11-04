from pydantic import BaseModel, Field


class RestoreRequest(BaseModel):
    """The commit to bring one configuration file back from."""

    commit: str = Field(pattern=r"^[0-9a-f]{7,40}$")
