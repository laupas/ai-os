from aios.variables.variable_field import VariableField
from aios.variables.variable_resolver import VariableResolver


class VariableFieldState:
    """What the console shows of a field: where its value comes from, and the value
    itself unless it is a secret. Read when asked, so it is always current."""

    def __init__(self, resolver: VariableResolver) -> None:
        self._resolver = resolver

    def value(self, field: VariableField, typed: str | None = None) -> str | None:
        """`typed` (not saved yet) wins, then the Variable or environment, then the
        field's default."""
        return typed or self._resolver.value_of(field.variable) or field.default

    def row(self, field: VariableField) -> dict:
        source = self._resolver.source_of(field.variable)
        return {
            **field.model_dump(exclude={"default"} if field.secret else set()),
            "source": source or ("default" if field.default else None),
            "value": None if field.secret else self.value(field),
        }

    def missing(self, fields: list[VariableField]) -> list[str]:
        return [f.variable for f in fields if f.required and not self.value(f)]
