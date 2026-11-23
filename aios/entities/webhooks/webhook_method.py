from enum import StrEnum


class WebhookMethod(StrEnum):
    """The HTTP method a webhook destination is called with. GET sends no body."""

    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    GET = "GET"
