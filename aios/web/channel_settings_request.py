from pydantic import BaseModel


class ChannelSettingsRequest(BaseModel):
    """A channel as the console's Settings send it: on or off (None leaves it), and
    values by variable name; a value left out or empty keeps the stored one."""

    enabled: bool | None = None
    values: dict[str, str] = {}
