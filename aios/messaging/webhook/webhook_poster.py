import asyncio
from typing import Any

import aiohttp
from jsonschema import Draft202012Validator

from aios.entities.webhooks.webhook_destination import WebhookDestination
from aios.messaging.delivery_result import DeliveryResult
from aios.messaging.webhook.webhook_template import WebhookTemplate
from aios.messaging.webhook.webhook_template_error import WebhookTemplateError

TIMEOUT_SECONDS = 20


class WebhookPoster:
    """Posts fields to a webhook destination: checks them against its `fields`
    schema, fills the templates and makes the request. A failure is reported back,
    never swallowed; the answer's text (cut short) is the detail either way."""

    def __init__(self, template: WebhookTemplate, enabled: bool) -> None:
        self._template = template
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        """Whether the webhook channel is on; the console's test works either way."""
        return self._enabled

    def missing(self, destination: WebhookDestination) -> list[str]:
        """The Variables its templates name that are set nowhere."""
        return self._template.missing(destination)

    @staticmethod
    def problems(destination: WebhookDestination, fields: dict[str, Any]) -> list[str]:
        """What is wrong with `fields` for this destination; empty when nothing is."""
        validator = Draft202012Validator(destination.fields)
        return [
            f"{'.'.join(str(p) for p in e.absolute_path) or 'fields'}: {e.message}"
            for e in validator.iter_errors(fields)
        ]

    async def post(self, destination: WebhookDestination, fields: dict[str, Any]) -> DeliveryResult:
        problems = self.problems(destination, fields)
        if problems:
            return DeliveryResult(ok=False, detail="; ".join(problems))
        try:
            call = self._template.render(destination, fields)
        except WebhookTemplateError as exc:
            return DeliveryResult(ok=False, detail=str(exc))
        try:
            async with (
                asyncio.timeout(TIMEOUT_SECONDS),
                aiohttp.ClientSession() as session,
                session.request(
                    call.method.value,
                    call.url,
                    headers=call.headers,
                    json=call.json_body,
                    data=call.text_body,
                ) as response,
            ):
                detail = await response.text()
                return DeliveryResult(
                    ok=response.status < 300, detail=f"{response.status} {detail[:500]}".strip()
                )
        except TimeoutError:
            return DeliveryResult(ok=False, detail=f"no answer within {TIMEOUT_SECONDS} s")
        except (aiohttp.ClientError, ValueError) as exc:
            return DeliveryResult(ok=False, detail=f"{destination.id} unreachable: {exc}")
