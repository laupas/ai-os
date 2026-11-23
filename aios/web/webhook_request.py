from typing import Any

from pydantic import BaseModel

from aios.entities.webhooks.webhook_approval import WebhookApproval
from aios.entities.webhooks.webhook_method import WebhookMethod


class WebhookRequest(BaseModel):
    """A webhook destination as the console sends it. `name` is read only when
    creating one; the rest is checked by `WebhookDestination`."""

    name: str | None = None
    description: str = ""
    method: WebhookMethod = WebhookMethod.POST
    url: str
    headers: dict[str, str] = {}
    fields: dict[str, Any]
    body: Any = None
    approval: WebhookApproval = WebhookApproval.ASK
    enabled: bool = True
