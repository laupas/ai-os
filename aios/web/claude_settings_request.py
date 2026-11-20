from typing import Literal

from pydantic import BaseModel


class ClaudeSettingsRequest(BaseModel):
    """How ai-os signs in to Claude, as the console's Settings send it. `value` is
    the token or key for `auth`; left out, the stored one is kept."""

    auth: Literal["subscription", "api_key"]
    value: str | None = None
