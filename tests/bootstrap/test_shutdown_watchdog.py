import threading

from aios.bootstrap import shutdown_watchdog
from aios.bootstrap.shutdown_watchdog import ShutdownWatchdog


def test_a_process_that_does_not_end_is_ended(monkeypatch) -> None:
    ended = threading.Event()
    monkeypatch.setattr(shutdown_watchdog.os, "_exit", lambda code: ended.set())
    ShutdownWatchdog(seconds=0.05).arm()
    assert ended.wait(2)
