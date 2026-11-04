from pydantic import BaseModel


class AgentConfig(BaseModel):
    model: str | None = None
    """None uses the Claude Code default."""

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
