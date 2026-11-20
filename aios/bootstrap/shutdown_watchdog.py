import logging
import os
import threading

log = logging.getLogger(__name__)


class ShutdownWatchdog:
    """Ends the process if it has not ended `seconds` after it was asked to.

    ai-os restarts by ending, and docker's restart policy starts it again. A library
    that hangs while shutting down (a socket never closed, a thread never joined)
    would leave it running but deaf, and nothing would restart it. Armed once the
    application has returned, this ends it hard instead.
    """

    def __init__(self, seconds: float = 30) -> None:
        self._seconds = seconds

    def arm(self) -> None:
        timer = threading.Timer(self._seconds, self._end)
        timer.daemon = True  # an orderly exit does not wait for it
        timer.start()

    def _end(self) -> None:
        log.error("ai-os did not end within %d s of shutting down; ending it now", self._seconds)
        logging.shutdown()
        os._exit(1)
