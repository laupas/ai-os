from pydantic import BaseModel


class ProgressEvent(BaseModel):
    """Something the agent started doing, worded for a human."""

    label: str
    tool_name: str
