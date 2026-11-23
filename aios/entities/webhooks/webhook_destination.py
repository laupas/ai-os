import re
from typing import Any

from jsonschema import Draft202012Validator, SchemaError
from pydantic import BaseModel, model_validator

from aios.entities.webhooks.webhook_approval import WebhookApproval
from aios.entities.webhooks.webhook_method import WebhookMethod

FIELD = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class WebhookDestination(BaseModel):
    """Somewhere agents can post to with `send_webhook`: an n8n flow, a Home
    Assistant automation, a chat's incoming webhook. `id` is its name.

    `url`, `headers` and `body` are templates: `{{field}}` is a value the agent
    gives, as declared in `fields`; `${VAR}` is a Variable from the console (or the
    environment), so a token never sits in the configuration repository. A `body`
    that is a mapping or list is sent as JSON, and a string that is exactly one
    `{{field}}` keeps the field's JSON type; a `body` that is a string is sent as
    written.
    """

    id: str
    description: str = ""
    """What the destination is for, read by agents to pick it."""
    method: WebhookMethod = WebhookMethod.POST
    url: str
    headers: dict[str, str] = {}
    fields: dict[str, Any] = {
        "type": "object",
        "properties": {"text": {"type": "string", "description": "The message"}},
        "required": ["text"],
    }
    """JSON schema of what the agent gives: an object, one property per field."""
    body: Any = {"text": "{{text}}"}
    approval: WebhookApproval = WebhookApproval.ASK
    enabled: bool = True

    @model_validator(mode="after")
    def _check(self) -> "WebhookDestination":
        if not self.url.startswith(("http://", "https://", "${")):
            raise ValueError("`url` must start with http:// or https://")
        if self.fields.get("type") != "object":
            raise ValueError('`fields` must be a JSON schema with "type": "object"')
        try:
            Draft202012Validator.check_schema(self.fields)
        except SchemaError as exc:
            raise ValueError(f"`fields` is not a valid JSON schema: {exc.message}") from exc
        declared = set(self.fields.get("properties", {}))
        unknown = sorted(self.placeholders() - declared)
        if unknown:
            raise ValueError(f"the templates use fields not declared in `fields`: {unknown}")
        if self.method is WebhookMethod.GET and self.body not in (None, "", {}):
            raise ValueError("a GET sends no body: leave `body` empty")
        return self

    def placeholders(self) -> set[str]:
        """Every `{{field}}` the templates use."""
        found: set[str] = set()

        def scan(value: Any) -> None:
            if isinstance(value, str):
                found.update(FIELD.findall(value))
            elif isinstance(value, list):
                for v in value:
                    scan(v)
            elif isinstance(value, dict):
                for v in value.values():
                    scan(v)

        scan([self.url, self.headers, self.body])
        return found
