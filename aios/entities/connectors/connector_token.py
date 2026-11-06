from datetime import datetime
from typing import Any

from pydantic import BaseModel, model_validator


class ConnectorToken(BaseModel):
    """The OAuth sign-in of one connector for one account: the tokens, and what is
    needed to renew them. A secret: kept in the data dir, never in the configuration
    repository and never sent to the console.

    `id` is `<connector>.shared` or `<connector>.user.<user_id>` (a connector name has
    no dot). `access_token`, `refresh_token` and `client_secret` are encrypted at rest
    when `encrypted` is set; `ConnectorTokens` is the only reader and writer.
    """

    id: str
    connector: str
    user_id: str | None = None
    """Whose account this is; None for the shared one."""
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    token_endpoint: str
    client_id: str
    client_secret: str | None = None
    auth_method: str = "none"
    """How the client authenticates at the token endpoint: client_secret_basic,
    client_secret_post or none."""
    resource: str | None = None
    signed_in_by: str | None = None
    signed_in_at: datetime | None = None
    encrypted: bool = False

    @model_validator(mode="before")
    @classmethod
    def _read_older_documents(cls, data: Any) -> Any:
        # Before 2026-11-06 there was one token per connector, its id the connector's
        # name. It is the shared sign-in; `ConnectorTokenMigration` moves it.
        if isinstance(data, dict) and "connector" not in data and "id" in data:
            return {**data, "connector": data["id"]}
        return data
