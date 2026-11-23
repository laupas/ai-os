import json
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from aios.entities.webhooks.webhook_destination import WebhookDestination
from aios.messaging.webhook.webhook_call import WebhookCall
from aios.messaging.webhook.webhook_template_error import WebhookTemplateError
from aios.variables.variable_resolver import VariableResolver

# `${VAR}` and `{{field}}` in one pass, so a field's value is never read again for
# a `${VAR}`: an agent cannot pull a secret into a request by writing one.
PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
WHOLE_FIELD = re.compile(r"^\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}$")


class WebhookTemplate:
    """Fills a destination's url, headers and body with Variables and the fields
    an agent gave. In the url a field is percent-encoded, in a header it loses its
    line breaks; a Variable is put in as it is."""

    def __init__(self, resolver: VariableResolver) -> None:
        self._resolver = resolver

    def render(self, destination: WebhookDestination, fields: dict[str, Any]) -> WebhookCall:
        url = self._text(destination.url, fields, lambda v: quote(v, safe=""))
        headers = {
            k: self._text(v, fields, lambda v: v.replace("\r", " ").replace("\n", " "))
            for k, v in destination.headers.items()
        }
        body = destination.body
        if isinstance(body, str):
            return WebhookCall(
                method=destination.method,
                url=url,
                headers=headers,
                text_body=self._text(body, fields, lambda v: v) if body else None,
            )
        return WebhookCall(
            method=destination.method,
            url=url,
            headers=headers,
            json_body=self._structure(body, fields) if body not in (None, {}) else None,
        )

    def missing(self, destination: WebhookDestination) -> list[str]:
        """The Variables the templates name that are set nowhere."""
        return self._resolver.missing([destination.url, destination.headers, destination.body])

    def _structure(self, value: Any, fields: dict[str, Any]) -> Any:
        if isinstance(value, str):
            whole = WHOLE_FIELD.match(value)
            if whole:
                return fields.get(whole.group(1))
            return self._text(value, fields, lambda v: v)
        if isinstance(value, list):
            return [self._structure(v, fields) for v in value]
        if isinstance(value, dict):
            return {k: self._structure(v, fields) for k, v in value.items()}
        return value

    def _text(self, template: str, fields: dict[str, Any], escape: Callable[[str], str]) -> str:
        def replace(match: re.Match[str]) -> str:
            variable, field = match.group(1), match.group(2)
            if variable:
                value = self._resolver.value_of(variable)
                if value is None:
                    raise WebhookTemplateError(f"the Variable {variable} is not set")
                return value
            return escape(self._as_text(fields.get(field)))

        return PLACEHOLDER.sub(replace, template)

    @staticmethod
    def _as_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)
