from pydantic import BaseModel


class ChangeAuthor(BaseModel):
    """Who a configuration commit is attributed to."""

    name: str
    email: str
