from typing import Any

from aios.conversations.message_recorder import MessageRecorder
from aios.entities.conversations.message_role import MessageRole
from aios.entities.users.user import User
from aios.messaging.sender_directory import SenderDirectory
from aios.storage.collection import Collection
from aios.tools.aios_tool import AiosTool
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError


class SendMessageTool(AiosTool):
    """Sends a message to a known user. Whether that needs approval is decided by
    `SendMessageApprovalRule` before this runs."""

    NAME = "send_message"

    def __init__(
        self, users: Collection[User], senders: SenderDirectory, recorder: MessageRecorder
    ) -> None:
        self._users = users
        self._senders = senders
        self._recorder = recorder

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return (
            "Send a message to a known user, by name or alias, via one of: "
            f"{', '.join(self._senders.names()) or 'none enabled'}. "
            "Messages to users who are not trusted need the owner's approval, which is "
            "asked automatically."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "User name or alias"},
                "via": {"type": "string", "enum": self._senders.names() or ["none"]},
                "text": {"type": "string"},
                "subject": {"type": "string", "description": "Mail only"},
            },
            "required": ["recipient", "via", "text"],
        }

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        recipient, via = str(args["recipient"]), str(args["via"])
        user = self._users.find(lambda u: u.matches_name(recipient))
        if user is None:
            raise ToolError(f"No user called {recipient!r}.")
        account = user.account_for(via)
        if account is None:
            raise ToolError(f"{user.name} has no {via} account.")
        sender = self._senders.get(via)
        if sender is None:
            raise ToolError(f"Sending via {via} is not enabled.")
        result = await sender.send(account, str(args["text"]), args.get("subject"))
        outcome = "sent" if result.ok else f"FAILED ({result.detail})"
        await self._recorder.record(
            context.conversation_id,
            MessageRole.TOOL,
            f"{via} message to {user.name} ({account.address}) {outcome}:\n{args['text']}",
            context.binding.channel,
            context.user.id,
        )
        if not result.ok:
            raise ToolError(f"Sending failed: {result.detail}")
        return f"Sent to {user.name} via {via}."
