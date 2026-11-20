from pydantic import BaseModel, Field


class VariableField(BaseModel):
    """One value something needs, asked for in the console: a channel's token, a
    code connector's API key. It is the Variable `variable`, set in the console,
    else the environment variable of that name, else `default`."""

    variable: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    label: str
    hint: str = ""
    secret: bool = True
    """Stored encrypted and never shown again; a plain value is shown."""
    required: bool = True
    default: str | None = None
    placeholder: str = ""
