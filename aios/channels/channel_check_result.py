from pydantic import BaseModel


class ChannelCheckResult(BaseModel):
    """What trying a channel's values showed, without sending anything."""

    ok: bool
    detail: str = ""
