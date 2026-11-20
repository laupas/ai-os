from aios.engine.claude_credentials import ClaudeCredentials


class Resolver:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def value_of(self, name: str) -> str | None:
        return self.values.get(name)


def test_env_for_another_auth_blanks_the_configured_one() -> None:
    credentials = ClaudeCredentials(
        lambda: "subscription", Resolver({"CLAUDE_CODE_OAUTH_TOKEN": "tok"})
    )  # type: ignore[arg-type]
    assert credentials.env() == {"CLAUDE_CODE_OAUTH_TOKEN": "tok", "ANTHROPIC_API_KEY": ""}
    assert credentials.env_for("api_key", "key") == {
        "CLAUDE_CODE_OAUTH_TOKEN": "",
        "ANTHROPIC_API_KEY": "key",
    }
    assert credentials.env_for("api_key") == {
        "CLAUDE_CODE_OAUTH_TOKEN": "",
        "ANTHROPIC_API_KEY": "",
    }
