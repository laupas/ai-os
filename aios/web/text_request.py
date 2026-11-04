from pydantic import BaseModel, Field


class TextRequest(BaseModel):
    """A body carrying one piece of text: a chat message, a config file, a document."""

    text: str = Field(min_length=1)
