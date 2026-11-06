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
  deny:                    # never
    - mcp__gmail__send_email
"""


def test_reading_gives_only_what_the_file_sets() -> None:
    values = ConfigYamlEditor().values(TEXT)
    assert values["web"] == {"enabled": True, "access_aud": "abc"}
    assert "scheduler" not in values


def test_an_edit_keeps_every_comment_and_touches_only_what_changed() -> None:
    editor = ConfigYamlEditor()
    values = editor.values(TEXT)
    values["approval"]["deny"] = ["mcp__gmail__send_email", "mcp__gmail__delete_email"]
    values["scheduler"] = {"tick_seconds": 10}
    text = editor.apply(TEXT, values)
    assert "# ai-os configuration. Secrets are not here." in text
    assert "# add mail later" in text
    assert "# The web console." in text
    assert "# asked every time" in text
    assert "    - mcp__gmail__delete_email" in text
    assert editor.values(text) == values


def test_a_key_left_out_is_removed_so_its_default_applies() -> None:
    editor = ConfigYamlEditor()
    values = editor.values(TEXT)
    del values["senders"]
    del values["web"]["access_aud"]
    text = editor.apply(TEXT, values)
    assert "senders" not in text and "access_aud" not in text
    assert "enabled: true" in text


def test_nothing_changed_is_the_same_text() -> None:
    editor = ConfigYamlEditor()
    assert editor.apply(TEXT, editor.values(TEXT)) == TEXT


def test_an_empty_file_is_written_from_scratch() -> None:
    editor = ConfigYamlEditor()
    assert editor.values(editor.apply("", {"timezone": "UTC"})) == {"timezone": "UTC"}
