from pydantic import BaseModel, ConfigDict

from aios.variables.variable_field import VariableField


class StoreMeta(BaseModel):
    """An item's optional `store:` block: how the Store shows it and what it asks for.
    Never written into the configuration repository."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    category: str | None = None
    version: str | None = None
    """Raised on every change, so an installation can tell it has an older one."""
    author: str | None = None
    license: str | None = None
    homepage: str | None = None
    """Where the service or server it uses is documented."""
    tags: list[str] = []
    notes: str = ""
    """Markdown shown before installing: what to set up first."""
    variables: list[VariableField] = []
    """Asked for on install and saved as Variables."""
    requires: list[str] = []
    """Further items installed with it, as `<collection>/<id>` (`connectors/github`),
    beyond those it implies: an agent's connectors and skills, a trigger's agent."""
