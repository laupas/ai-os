from pydantic import BaseModel


class StoreInstallResult(BaseModel):
    installed: list[str] = []
    kept: list[str] = []
    missing: list[str] = []
    version: str | None = None
    """The version of the item installed."""
    moved_secrets: list[str] = []
    """Literal secrets found in a connector's config, now Variables."""
