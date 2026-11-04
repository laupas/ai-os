from datetime import datetime
from pathlib import Path

LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
MAX_LINES = 400


class LogReader:
    """Reads ai-os's own log file and its rotated siblings, oldest first.

    A line starts with `YYYY-MM-DD HH:MM:SS,mmm LEVEL`; continuation lines (e.g. a
    traceback) belong to the line above and are kept with it.
    """

    def __init__(self, log_file: Path) -> None:
        self._log_file = Path(log_file)

    def read(self, since: datetime, min_level: str = "WARNING") -> list[str]:
        wanted = set(LEVELS[LEVELS.index(min_level.upper()) :])
        cutoff = since.strftime("%Y-%m-%d %H:%M:%S")
        out: list[str] = []
        keep = False
        for line in self._lines():
            stamp, level = self._head(line)
            if stamp is not None:
                keep = stamp >= cutoff and level in wanted
            if keep:
                out.append(line)
        return out[-MAX_LINES:]

    def _lines(self) -> list[str]:
        files = [self._log_file.with_name(f"{self._log_file.name}.{n}") for n in range(5, 0, -1)]
        lines: list[str] = []
        for path in [*files, self._log_file]:
            if path.exists():
                lines += path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines

    @staticmethod
    def _head(line: str) -> tuple[str | None, str | None]:
        parts = line.split(" ", 3)
        if len(parts) >= 3 and len(parts[0]) == 10 and parts[0][4] == "-":
            return f"{parts[0]} {parts[1][:8]}", parts[2]
        return None, None
