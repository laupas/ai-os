import yaml

from aios.config.config_yaml_editor import ConfigYamlEditor

TEXT = """\
# ai-os configuration. Secrets are not here.
channels: [slack, web]
senders: [signal]          # add mail later

# The web console.
web:
  enabled: true
  access_aud: abc

approval:
  always:                  # asked every time
    - mcp__gcal__update-event
"""


def test_a_key_goes_into_its_section_and_every_comment_stays() -> None:
    text = ConfigYamlEditor().insert(TEXT, ["web", "port"], 8080)
    for comment in ["# ai-os configuration.", "# add mail later", "# The web console.", "# asked"]:
        assert comment in text
    assert yaml.safe_load(text)["web"] == {"enabled": True, "access_aud": "abc", "port": 8080}


def test_a_missing_section_is_created() -> None:
    text = ConfigYamlEditor().insert(TEXT, ["scheduler", "tick_seconds"], 30)
    assert "scheduler:\n  tick_seconds: 30" in text


def test_a_key_set_already_is_left_as_it_is() -> None:
    assert ConfigYamlEditor().insert(TEXT, ["web", "enabled"], False) == TEXT


def test_an_empty_file_gets_the_key() -> None:
    assert yaml.safe_load(ConfigYamlEditor().insert("", ["timezone"], "UTC")) == {"timezone": "UTC"}
