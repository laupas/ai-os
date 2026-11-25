from enum import StrEnum


class AppearanceMode(StrEnum):
    """Light or dark, or whatever the device is set to."""

    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"
