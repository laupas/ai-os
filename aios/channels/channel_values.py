from aios.channels.channel_type import ChannelType
from aios.variables.variable_field import VariableField
from aios.variables.variable_field_state import VariableFieldState
from aios.variables.variable_resolver import VariableResolver


class ChannelValues:
    """A channel's field values: the console's Variable, else the environment,
    else the field's default. Read when asked, so a restart picks up a change."""

    def __init__(self, resolver: VariableResolver) -> None:
        self._resolver = resolver
        self._state = VariableFieldState(resolver)

    def of(
        self, channel: ChannelType, overrides: dict[str, str] | None = None
    ) -> dict[str, str | None]:
        """`overrides` (values typed but not saved yet) win, for a check."""
        given = overrides or {}
        return {f.variable: self._state.value(f, given.get(f.variable)) for f in channel.fields}

    def source_of(self, variable: str) -> str | None:
        """`variable`, `environment`, or None."""
        return self._resolver.source_of(variable)

    def row(self, field: VariableField) -> dict:
        """The field as the console shows it."""
        return self._state.row(field)

    def missing(self, channel: ChannelType) -> list[str]:
        return self._state.missing(channel.fields)
