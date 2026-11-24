from pydantic import BaseModel

from aios.entities.users.audience_entry import AudienceEntry


class Agent(BaseModel):
    """An agent: what it is for, its prompt, and what it may use. `id` is its name.

    Stored in /data and edited in the console; the repo's `agents/*.md` only seed
    an empty store.
    """

    id: str
    description: str
    prompt: str
    model: str | None = None
    """None inherits the session's model."""
    enabled: bool = True
    builtin_tools: list[str] = []
    skills: list[str] = []
    connectors: dict[str, list[str] | None] = {}
    """Connector name to the tools granted on it; `None` as a value grants all."""
    available_to: list[AudienceEntry] | None = None
    """Who may talk to it or have it work for them: `everyone`, `group:<id>`,
    `role:<id>`, `user:<id>`. None: administrators only. The orchestrator is
    everyone's."""

    @property
    def name(self) -> str:
        return self.id
