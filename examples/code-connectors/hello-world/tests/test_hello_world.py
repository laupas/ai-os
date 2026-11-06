"""The connector's own tests. Run them with ai-os's Python, in the ai-os clone:
`uv run pytest <config>/code/hello-world/tests`."""

import json
import subprocess
import sys
from pathlib import Path

SERVER = Path(__file__).parents[1] / "server.py"


def _preflight(text: str, settings: dict | None = None) -> dict:
    env = {"AIOS_CONNECTOR_SETTINGS": json.dumps(settings or {})}
    result = subprocess.run(
        [sys.executable, str(SERVER), "preflight", "shout", json.dumps({"text": text})],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return json.loads(result.stdout)


def test_a_short_text_is_put_to_the_human() -> None:
    assert _preflight("hi") == {"ask": "Shout 'hi'?"}


def test_a_long_text_is_refused_before_anyone_is_asked() -> None:
    assert "too long" in _preflight("x" * 21)["deny"]


def test_the_limit_is_a_setting() -> None:
    assert "deny" in _preflight("hello", {"max_shout_length": 3})
