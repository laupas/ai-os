from datetime import datetime

from aios.logs.log_reader import LogReader


def test_filters_by_time_and_level_and_keeps_tracebacks(tmp_path) -> None:
    log = tmp_path / "aios.log"
    (tmp_path / "aios.log.1").write_text("2026-10-08 10:00:00,000 ERROR old boom\n")
    log.write_text(
        "2026-10-09 09:00:00,000 INFO x started\n"
        "2026-10-09 09:01:00,000 ERROR x failed\n"
        "Traceback (most recent call last):\n"
        "ValueError: bad\n"
        "2026-10-09 09:02:00,000 WARNING y slow\n"
    )
    reader = LogReader(log)
    lines = reader.read(datetime(2026, 10, 9, 0, 0))
    assert lines == [
        "2026-10-09 09:01:00,000 ERROR x failed",
        "Traceback (most recent call last):",
        "ValueError: bad",
        "2026-10-09 09:02:00,000 WARNING y slow",
    ]
    assert reader.read(datetime(2026, 10, 1), "ERROR")[0].endswith("old boom")
