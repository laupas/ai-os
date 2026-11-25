from pydantic import BaseModel, Field

from aios.entities.users.appearance import THEME_NAME
from aios.entities.users.appearance_mode import AppearanceMode


class AppearanceRequest(BaseModel):
    """The caller's own choice on the console's Appearance page."""

    mode: AppearanceMode
    theme: str = Field(pattern=THEME_NAME)
