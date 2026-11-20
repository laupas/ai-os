from pydantic import BaseModel


class CodeConnectorCheck(BaseModel):
    """What a code connector said about itself when asked `server.py check`."""

    ok: bool
    detail: str = ""
