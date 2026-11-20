from aios.engine.claude_cli_sign_in_check import NOISE


def test_only_the_cli_words_of_a_refusal_are_kept() -> None:
    raw = "Claude Code returned an error result: Invalid API key · Fix it (exit code: 1)"
    assert NOISE.sub("", raw) == "Invalid API key · Fix it"
