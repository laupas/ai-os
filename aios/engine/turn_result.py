from pydantic import BaseModel


class TurnResult(BaseModel):
    text: str
    session_id: str | None = None
    """The agent session to resume next turn."""
