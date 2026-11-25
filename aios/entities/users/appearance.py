from pydantic import BaseModel, Field

from aios.entities.users.appearance_mode import AppearanceMode

THEME_NAME = r"^[a-z][a-z0-9-]{0,31}$"


class Appearance(BaseModel):
    """How the console looks for one user, in every browser they sign in from.
    `id` is the user's id. `theme` names one of the console's colour themes; the
    console uses its default for a name it does not know."""

    id: str
    mode: AppearanceMode = AppearanceMode.SYSTEM
    theme: str = Field(default="indigo", pattern=THEME_NAME)
