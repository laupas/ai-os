from pydantic import BaseModel


class SetupStep(BaseModel):
    """One step of setting a channel up on the provider's side, as the console
    shows it: what to do, where (`link`, the provider's page for it), and what to
    watch out for while doing it (`details`)."""

    text: str
    link: str | None = None
    details: list[str] = []
