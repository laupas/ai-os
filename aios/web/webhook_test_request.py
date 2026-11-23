from typing import Any

from pydantic import BaseModel

from aios.web.webhook_request import WebhookRequest


class WebhookTestRequest(BaseModel):
    """A destination as typed in the console, saved or not, and sample fields to
    post to it."""

    destination: WebhookRequest
    fields: dict[str, Any] = {}
