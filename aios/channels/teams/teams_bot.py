import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from microsoft_teams.api import (
    Account,
    Attachment,
    CreateConversationParams,
    MessageActivity,
    MessageActivityInput,
)
from microsoft_teams.apps import ActivityContext, App
from microsoft_teams.apps.socket_mode.negotiate import NegotiateError, negotiate_service
from microsoft_teams.apps.socket_mode.transport import build_negotiate_url

log = logging.getLogger(__name__)

CARD = "application/vnd.microsoft.card.adaptive"
CHECK_GEO = "emea"
# Microsoft Entra's error codes for a refused bot sign-in, as the people setting it
# up meet them.
SIGN_IN_ERRORS = {
    "unauthorized_client": (
        "Microsoft does not know this bot id in this tenant. Use the bot's id from "
        "Developer Portal → Tools → Bot management, not the Teams app's App ID"
    ),
    "invalid_client": (
        "the client secret is wrong or has expired. Add a new one to the bot and enter it again"
    ),
    "invalid_request": "Microsoft refused the sign-in. Check the tenant id",
}


class TeamsBot:
    """The Teams SDK's app, in Socket Mode: it dials out to Teams, so no public
    address is needed. Everything ai-os does with Teams goes through here, with
    activities as Bot Framework JSON, so the rest knows nothing of the SDK.

    Socket Mode is a preview of the Teams SDK, and the bot must have it switched
    on in the Teams Developer Portal (Bot management, Delivery method).
    """

    def __init__(self, app_id: str, password: str, tenant_id: str) -> None:
        self._app = App(
            client_id=app_id, client_secret=password, tenant_id=tenant_id, socket_mode=True
        )
        self._ready = False
        self._lock = asyncio.Lock()

    async def run(self, on_activity: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        """Receives until stopped. `on_activity` must return quickly: Teams wants each
        activity acknowledged within 25 seconds, and that happens when it returns."""

        @self._app.on_message
        async def on_message(ctx: ActivityContext[MessageActivity]) -> None:
            await on_activity(
                ctx.activity.model_dump(mode="json", by_alias=True, exclude_none=True)
            )

        await self._initialize()
        await self._app.start()

    async def send_text(self, service_url: str, conversation_id: str, text: str) -> str:
        message = MessageActivityInput(text=text, text_format="markdown")
        return await self._send(service_url, conversation_id, message)

    async def send_card(
        self, service_url: str, conversation_id: str, card: dict[str, Any], summary: str
    ) -> str:
        return await self._send(service_url, conversation_id, self._card(card, summary))

    async def update_card(
        self,
        service_url: str,
        conversation_id: str,
        activity_id: str,
        card: dict[str, Any],
        summary: str,
    ) -> None:
        await self._initialize()
        await self._app.api.conversations.update_activity(
            conversation_id, activity_id, self._card(card, summary), service_url=service_url
        )

    async def open_personal_chat(self, tenant_id: str, user_id: str) -> str:
        """The personal chat with a user who has the app installed; `user_id` is their
        Microsoft Entra object id. Returns the conversation id."""
        await self._initialize()
        conversation = await self._app.api.conversations.create(
            CreateConversationParams(
                members=[Account(id=user_id)],
                tenant_id=tenant_id,
                channel_data={"tenant": {"id": tenant_id}},
            )
        )
        return str(conversation.id)

    async def check(self) -> str:
        """Signs in and asks Teams for a socket, without opening it. Raises when the
        bot cannot sign in or Socket Mode is not on for it."""
        try:
            token = await self._app.token_provider.get_app_token()
        except Exception as exc:
            raise RuntimeError(SIGN_IN_ERRORS.get(str(exc), f"sign-in failed: {exc}")) from exc
        if token is None:
            raise RuntimeError("the bot could not sign in; check the app id, secret and tenant")

        async def bot_token() -> str:
            return str(token)

        try:
            await negotiate_service(build_negotiate_url(CHECK_GEO), bot_token)
        except NegotiateError as exc:
            if exc.status_code == 403:
                raise RuntimeError(
                    "the bot signed in, but Socket Mode is not on for it (Developer Portal → "
                    "Bot management → Configure → Delivery method)"
                ) from exc
            raise RuntimeError(str(exc)) from exc
        return "the bot signed in and Teams offers it a socket"

    async def _initialize(self) -> None:
        """Sending needs the app initialized, whether or not it is receiving yet."""
        async with self._lock:
            if not self._ready:
                await self._app.initialize()
                self._ready = True

    async def _send(self, service_url: str, conversation_id: str, message: Any) -> str:
        await self._initialize()
        sent = await self._app.send(conversation_id, message, service_url=service_url)
        return sent.id

    @staticmethod
    def _card(card: dict[str, Any], summary: str) -> MessageActivityInput:
        message = MessageActivityInput(summary=summary)
        return message.add_attachments(Attachment(content_type=CARD, content=card))
