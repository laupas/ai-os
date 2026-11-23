import hashlib
import hmac
import secrets


class WebhookToken:
    """The token a caller sends to start a trigger. Only its SHA-256 is stored;
    the token itself is shown once, when it is made."""

    PREFIX = "aios_"

    @staticmethod
    def new() -> str:
        return WebhookToken.PREFIX + secrets.token_urlsafe(32)

    @staticmethod
    def hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def matches(token: str, sha256: str | None) -> bool:
        return sha256 is not None and hmac.compare_digest(WebhookToken.hash(token), sha256)
