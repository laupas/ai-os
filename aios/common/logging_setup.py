import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class LoggingSetup:
    """Configures process-wide logging once at startup: to stderr, and to a rotating
    file the log-checker agent can read."""

    def __init__(self, level: str, log_file: Path | None = None) -> None:
        self._level = level
        self._log_file = log_file

    def configure(self) -> None:
        handlers: list[logging.Handler] = [logging.StreamHandler()]
        if self._log_file is not None:
            try:
                self._log_file.parent.mkdir(parents=True, exist_ok=True)
                handlers.append(
                    RotatingFileHandler(self._log_file, maxBytes=5_000_000, backupCount=5)
                )
            except OSError as exc:
                print(f"logging to file disabled: {exc}")
        logging.basicConfig(level=self._level.upper(), format=FORMAT, handlers=handlers)
        for noisy in ("httpx", "httpcore", "slack_bolt", "slack_sdk", "aiohttp"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
