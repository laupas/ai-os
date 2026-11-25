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


def test_set_replaces_a_value_and_keeps_its_comment() -> None:
    text = ConfigYamlEditor().set(
        "agent:\n  auth: subscription  # how\n", ["agent", "auth"], "api_key"
    )
    assert yaml.safe_load(text) == {"agent": {"auth": "api_key"}}
    assert "# how" in text


def test_set_to_the_same_value_leaves_the_text_alone() -> None:
    text = "agent:\n  auth: 'subscription'\n"
    assert ConfigYamlEditor().set(text, ["agent", "auth"], "subscription") == text


def test_a_section_is_merged_so_the_comments_on_what_stays_stay() -> None:
    text = ConfigYamlEditor().replace_section(
        TEXT,
        "approval",
        {"always": ["mcp__gcal__update-event", "mcp__x__y"], "timeout_seconds": 60},
    )
    assert "# asked every time" in text
    assert "# The web console." in text
    assert yaml.safe_load(text)["approval"] == {
        "always": ["mcp__gcal__update-event", "mcp__x__y"],
        "timeout_seconds": 60,
    }


def test_keys_left_out_of_a_section_are_removed_and_none_removes_it() -> None:
    editor = ConfigYamlEditor()
    text = editor.replace_section(TEXT, "web", {"enabled": False})
    assert yaml.safe_load(text)["web"] == {"enabled": False}
    gone = editor.replace_section(TEXT, "approval", None)
    assert "approval" not in yaml.safe_load(gone)
    assert editor.replace_section(TEXT, "scheduler", None) == TEXT


def test_the_comment_above_the_next_section_stays_with_it() -> None:
    text = "approval:\n  deny:\n    - a\n\n# About the agent.\nagent:\n  auth: api_key\n"
    grown = ConfigYamlEditor().replace_section(text, "approval", {"deny": ["a", "b"]})
    assert (
        grown
        == "approval:\n  deny:\n    - a\n    - b\n\n# About the agent.\nagent:\n  auth: api_key\n"
    )
    gone = ConfigYamlEditor().replace_section(text, "agent", None)
    assert gone == "approval:\n  deny:\n    - a\n"


def test_a_section_goes_into_a_file_written_as_json() -> None:
    text = (
        '{"channels":["web"],"web":{"public_url":"https://x.example","auth":{"mode":"password"}}}\n'
    )
    sso = {"mode": "sso", "providers": [{"kind": "microsoft", "tenant": "example.com"}]}
    edited = ConfigYamlEditor().replace_section(text, "web", {"auth": sso})
    assert yaml.safe_load(edited) == {"channels": ["web"], "web": {"auth": sso}}
