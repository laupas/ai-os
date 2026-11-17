from pydantic import BaseModel, Field


class MessageRequest(BaseModel):
    """A chat message written into a web conversation."""

    text: str = Field(min_length=1)
    voice: bool = False
    """The text is a transcript, and the reply will be read aloud."""
