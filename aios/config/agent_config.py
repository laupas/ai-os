from typing import Literal

from pydantic import BaseModel, ConfigDict


class AgentConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    model: str | None = None
    """None uses the Claude Code default."""

    auth: Literal["subscription", "api_key"] = "subscription"
    """How ai-os signs in to Claude: `subscription` with a Claude Code token
    (`claude setup-token`, the variable CLAUDE_CODE_OAUTH_TOKEN), `api_key` with an
    Anthropic API key (the variable ANTHROPIC_API_KEY). Set the value on the
    Variables page, as a secret; the process environment is the fallback."""

    builtin_tools: list[str] = [
        "Task",
        "Skill",
        "WebSearch",
        "WebFetch",
        "TodoWrite",
        "Read",
        "Grep",
        "Glob",
        "Edit",
        "Write",
    ]
    """Built-in Claude Code tools agents may use. Never Bash. The file tools only reach
    the folders under `files` in config.yaml, and nothing when none are set. This is
    the most any agent may get: each agent's own built-in tools are a subset."""

    turn_timeout_seconds: int = 600
