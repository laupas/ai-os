from pydantic import BaseModel

from aios.variables.secrets_key_origin import SecretsKeyOrigin


class SecretsStatus(BaseModel):
    """The key in use and the secrets it opens, for Settings → Security."""

    origin: SecretsKeyOrigin
    fingerprint: str
    previous_fingerprints: list[str]
    legacy_file: bool
    """`<data>/secrets.key` of an older ai-os is still there."""
    total: int
    on_previous: int
    """Opened only by a previous key: moved over at the next start."""
    unreadable: list[str]
    """Opened by no key: "variable API_TOKEN". Lost unless the right key comes back."""
