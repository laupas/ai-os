import re

PART = re.compile(r"\d+|[^\d.]+")


class StoreVersion:
    """Compares versions such as `1.2.0`: number by number, so 1.10 is newer than
    1.9; a part that is not a number compares as text."""

    @staticmethod
    def newer(candidate: str | None, than: str | None) -> bool:
        if not candidate or not than:
            return False
        return StoreVersion._key(candidate) > StoreVersion._key(than)

    @staticmethod
    def _key(version: str) -> list[tuple[int, int | str]]:
        parts = PART.findall(version.strip().removeprefix("v"))
        return [(1, int(p)) if p.isdigit() else (0, p) for p in parts]
