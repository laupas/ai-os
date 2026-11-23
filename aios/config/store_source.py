from pydantic import BaseModel, field_validator

SCHEMES = ("https://", "file://")


class StoreSource(BaseModel):
    """A git repository the Store offers agents, skills, connectors and triggers from."""

    url: str
    """An `https://` git URL (`file://` for a local one)."""
    branch: str | None = None
    """None is the repository's default branch."""

    @field_validator("url")
    @classmethod
    def _known_scheme(cls, url: str) -> str:
        url = url.strip()
        if not url.startswith(SCHEMES):
            raise ValueError("a store source is an https:// git URL")
        return url
