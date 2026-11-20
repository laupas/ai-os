from typing import Literal

from aios.web.claude_sign_in_check import ClaudeSignInCheck
from aios.web.sign_in_check_result import SignInCheckResult


class FakeClaudeSignInCheck(ClaudeSignInCheck):
    """Accepts only the values in `good`, and records what it was asked."""

    def __init__(self, good: set[str] | None = None) -> None:
        self.good = good or set()
        self.asked: list[tuple[str, str | None]] = []

    async def check(
        self, auth: Literal["subscription", "api_key"], value: str | None = None
    ) -> SignInCheckResult:
        self.asked.append((auth, value))
        if value in self.good:
            return SignInCheckResult(ok=True, model="claude-haiku")
        return SignInCheckResult(ok=False, error="the token or key was refused")
