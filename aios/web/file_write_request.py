from pydantic import BaseModel, Field


class FileWriteRequest(BaseModel):
    """A file written from the console's repository view: on which branch, its
    text (None to delete it), the blob id it was opened at (None for a new file),
    and the commit message."""

    branch: str = Field(min_length=1)
    path: str = Field(min_length=1)
    text: str | None = None
    base: str | None = None
    message: str = ""
