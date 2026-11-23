from typing import Any

from pydantic import BaseModel

from aios.entities.webhooks.webhook_method import WebhookMethod


class WebhookCall(BaseModel):
    """A destination's templates filled in: the HTTP request about to be made.
    Holds resolved secrets, so it is never logged or shown."""

    method: WebhookMethod
    url: str
    headers: dict[str, str]
    json_body: Any = None
    text_body: str | None = None
