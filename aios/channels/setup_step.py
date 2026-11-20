from pydantic import BaseModel


class SetupStep(BaseModel):
    """One step of setting a channel up on the provider's side, as the console
    shows it: what to do, and where (`link`, the provider's page for it)."""

    text: str
    link: str | None = None
