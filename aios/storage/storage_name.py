import re

_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class StorageName:
    """Validates names that become path segments, so no id can escape the data dir."""

    @staticmethod
    def check(name: str) -> str:
        if not _SEGMENT.match(name) or ".." in name:
            raise ValueError(f"invalid storage name: {name!r}")
        return name

    @staticmethod
    def check_path(path: str) -> str:
        for segment in path.split("/"):
            StorageName.check(segment)
        return path
