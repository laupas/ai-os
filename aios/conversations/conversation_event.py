from pydantic import BaseModel

from aios.entities.conversations.message import Message


class ConversationEvent(BaseModel):
    """Something that happened in a conversation, for whoever is watching it live.

    `kind` is `message` (`message` was recorded), `progress` (the agent started
    doing `text`), `delta` (the agent wrote `text`; `restart` means a new reply
    began and what was streamed so far is superseded), `done` (the turn ended) or
    `approval` (a question `approval_id` with `options`).
    """

    conversation_id: str
    kind: str
    text: str = ""
    restart: bool = False
    message: Message | None = None
    approval_id: str | None = None
    options: list[str] = []
