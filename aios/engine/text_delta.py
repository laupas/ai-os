from pydantic import BaseModel


class TextDelta(BaseModel):
    """A piece of the reply as the agent writes it. `restart` marks the first piece
    of a new assistant message, which supersedes what was streamed before it (the
    agent's words before a tool call are not its answer)."""

    text: str
    restart: bool = False
