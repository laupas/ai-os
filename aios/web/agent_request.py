from pydantic import BaseModel


class AgentRequest(BaseModel):
    """An agent as the console sends it. `name` is read only when creating one; on a
    change, fields left out keep their value."""

    name: str | None = None
    description: str | None = None
    prompt: str | None = None
    model: str | None = None
    enabled: bool = True
    builtin_tools: list[str] = []
    skills: list[str] = []
    connectors: dict[str, list[str] | None] = {}
