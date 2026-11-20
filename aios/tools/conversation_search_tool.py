from datetime import timedelta
from typing import Any

from aios.common.clock import Clock
from aios.conversations.message_recorder import MessageRecorder
from aios.entities.conversations.conversation import Conversation
from aios.entities.conversations.message import Message
from aios.entities.conversations.message_role import MessageRole
from aios.storage.collection import Collection
from aios.tools.aios_tool import AiosTool
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError

MAX_RESULTS = 20
SNIPPET_CHARS = 400


class ConversationSearchTool(AiosTool):
    """Searches the turn user's own earlier conversations.

    Only conversations the user took part in are read: the check is on
    `participants` here, in code, and does not depend on the collection's
    definition, which an installation can override. The current conversation is
    left out, since it is already in the agent's context.
    """

    def __init__(
        self, conversations: Collection[Conversation], recorder: MessageRecorder, clock: Clock
    ) -> None:
        self._conversations = conversations
        self._recorder = recorder
        self._clock = clock

    @property
    def name(self) -> str:
        return "conversation_search"

    @property
    def description(self) -> str:
        return (
            "Search the user's own earlier conversations with ai-os. `query` keeps messages "
            "containing all of its words (any case). `days` limits to the last days. "
            "`conversation_id` searches only that conversation; without a query it returns "
            f"its messages. Newest first, at most {MAX_RESULTS}, long messages shortened."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "days": {"type": "number"},
                "conversation_id": {"type": "string"},
            },
        }

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        words = str(args.get("query") or "").lower().split()
        only = args.get("conversation_id")
        if not words and not only:
            raise ToolError("Give a query, a conversation_id, or both.")
        own = self._conversations.filter(
            lambda c: context.user.id in c.participants and c.id != context.conversation_id
        )
        if only:
            own = [c for c in own if c.id == only]
            if not own:
                raise ToolError(f"No earlier conversation of yours with id {only!r}.")
        since = (
            self._clock.now() - timedelta(days=float(args["days"])) if args.get("days") else None
        )
        hits: list[tuple[Conversation, Message]] = []
        for conversation in own:
            for message in await self._recorder.history(conversation.id):
                if message.role is MessageRole.ACTIVITY:
                    continue
                if since is not None and message.created_at < since:
                    continue
                text = message.text.lower()
                if all(w in text for w in words):
                    hits.append((conversation, message))
        if not hits:
            return "No matching messages."
        hits.sort(key=lambda hit: hit[1].created_at, reverse=True)
        return "\n\n".join(self._format(c, m, words) for c, m in hits[:MAX_RESULTS])

    @staticmethod
    def _format(conversation: Conversation, message: Message, words: list[str]) -> str:
        title = f" ({conversation.title})" if conversation.title else ""
        when = message.created_at.strftime("%Y-%m-%d %H:%M UTC")
        head = f"[{when}] conversation {conversation.id}{title}, {message.role.value}:"
        return f"{head}\n{ConversationSearchTool._snippet(message.text, words)}"

    @staticmethod
    def _snippet(text: str, words: list[str]) -> str:
        if len(text) <= SNIPPET_CHARS:
            return text
        found = [i for i in (text.lower().find(w) for w in words) if i >= 0]
        start = max(0, min(found, default=0) - SNIPPET_CHARS // 4)
        end = start + SNIPPET_CHARS
        return f"{'…' if start else ''}{text[start:end]}{'…' if end < len(text) else ''}"
