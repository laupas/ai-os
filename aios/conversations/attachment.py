from pydantic import BaseModel


class Attachment(BaseModel):
    name: str
    mime_type: str
    url: str | None = None
