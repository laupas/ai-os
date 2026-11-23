from pydantic import BaseModel


class StoreUninstallResult(BaseModel):
    removed: list[str] = []
    """The item, and for a code connector its files under `code/`."""
    still_used_by: list[str] = []
    """What refers to it and stays: an agent granted the removed connector, a
    trigger that runs the removed agent. Left for the administrator to change."""
