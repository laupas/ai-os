import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Literal

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultError,
    ResultMessage,
    query,
)

from aios.engine.claude_credentials import ClaudeCredentials
from aios.web.claude_sign_in_check import ClaudeSignInCheck
from aios.web.sign_in_check_result import SignInCheckResult

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 60
MODEL = "haiku"  # the cheapest call that proves the sign-in works
ERRORS = {
    "authentication_failed": "the token or key was refused",
    "billing_error": "signed in, but the account cannot pay for the call (credits or plan)",
    "rate_limit": "signed in, but rate limited right now",
}
# What the SDK wraps around the CLI's own words, which are the useful part.
NOISE = re.compile(r"^Claude Code returned an error result: |\s*\(exit code: \d+\)$")


class ClaudeCliSignInCheck(ClaudeSignInCheck):
    """Sends one short message through the same CLI a turn uses, with nothing
    else: no tools, no connectors, no project settings. Costs a few tokens."""

    def __init__(self, credentials: ClaudeCredentials, repo_dir: Path) -> None:
        self._credentials = credentials
        self._repo_dir = Path(repo_dir)

    async def check(
        self, auth: Literal["subscription", "api_key"], value: str | None = None
    ) -> SignInCheckResult:
        env = self._credentials.env_for(auth, value)
        if not env[self._credentials.variable_for(auth)]:
            return SignInCheckResult(ok=False, error="nothing to try: no token or key is set")
        options = ClaudeAgentOptions(
            cwd=str(self._repo_dir),
            setting_sources=[],
            tools=[],
            allowed_tools=[],
            mcp_servers={},
            strict_mcp_config=True,
            max_turns=1,
            model=MODEL,
            env=env,
        )
        started = time.monotonic()
        model: str | None = None
        error: str | None = None
        try:
            async with asyncio.timeout(TIMEOUT_SECONDS):
                async for message in query(prompt="Reply with the word OK.", options=options):
                    if isinstance(message, AssistantMessage):
                        model = model or message.model
                        if message.error:
                            error = error or ERRORS.get(message.error, message.error)
                    elif isinstance(message, ResultMessage) and message.is_error:
                        error = error or message.result or "; ".join(message.errors or [])
        except TimeoutError:
            error = f"no answer within {TIMEOUT_SECONDS} seconds"
        except ResultError as exc:  # a refused credential: expected, not worth a traceback
            error = error or NOISE.sub("", str(exc))
        except Exception as exc:
            log.exception("checking the Claude sign-in failed")
            error = str(exc)
        return SignInCheckResult(
            ok=error is None,
            error=error,
            model=None if error else model,
            seconds=round(time.monotonic() - started, 1),
        )
