import pytest
from pydantic import ValidationError

from aios.config.app_config import AppConfig


def test_bash_is_never_a_builtin_tool() -> None:
    with pytest.raises(ValidationError, match="Bash"):
        AppConfig.model_validate({"agent": {"builtin_tools": ["Read", "Bash"]}})


def test_an_unknown_timezone_is_refused() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        AppConfig.model_validate({"timezone": "Europe/Zurch"})
    assert AppConfig.model_validate({"timezone": "America/New_York"}).timezone == "America/New_York"
