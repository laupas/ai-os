from abc import ABC, abstractmethod
from typing import Literal

from aios.web.sign_in_check_result import SignInCheckResult


class ClaudeSignInCheck(ABC):
    """Tries one way of signing in to Claude: `value` when given, else the stored one."""

    @abstractmethod
    async def check(
        self, auth: Literal["subscription", "api_key"], value: str | None = None
    ) -> SignInCheckResult: ...
