from collections import OrderedDict

LIMIT = 50


class GroupValuesSeen:
    """The group values each sign-in provider sent lately, so Settings can offer
    them for the mapping instead of having them typed. Only the values, never who
    sent them; kept in memory, so a restart forgets them until the next sign-ins."""

    def __init__(self) -> None:
        self._seen: dict[str, OrderedDict[str, None]] = {}

    def record(self, provider: str, values: list[str]) -> None:
        seen = self._seen.setdefault(provider, OrderedDict())
        for value in values:
            seen.pop(value, None)
            seen[value] = None
        while len(seen) > LIMIT:
            seen.popitem(last=False)

    def all(self) -> dict[str, list[str]]:
        return {provider: sorted(values) for provider, values in self._seen.items()}
