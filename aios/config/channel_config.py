from pydantic import BaseModel, ConfigDict


class ChannelConfig(BaseModel):
    """One channel in aios.yaml. Its values (tokens, numbers, addresses) are not
    here: they are Variables in the console, or the environment."""

    model_config = ConfigDict(use_attribute_docstrings=True, extra="forbid")

    enabled: bool = True
