from typing import Any

from aios.approvals.approval_service import ApprovalService
from aios.tools.aios_tool import AiosTool
from aios.tools.tool_context import ToolContext


class AskHumanTool(AiosTool):
    """Lets an agent hand a decision to the user and wait for the answer."""

    def __init__(self, approvals: ApprovalService) -> None:
        self._approvals = approvals

    @property
    def name(self) -> str:
        return "ask_human"

    @property
    def description(self) -> str:
        return (
            "Ask the user to decide something and wait for the answer. Use it for choices "
            "that are the user's to make. Give 2-5 short options."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "options": {"type": "array", "items": {"type": "string"}, "minItems": 2},
            },
            "required": ["question", "options"],
        }

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        answer = await self._approvals.request(
            context.conversation_id,
            context.binding,
            str(args["question"]),
            [str(o) for o in args["options"]],
        )
        return f"The user answered: {answer}" if answer else "The user did not answer in time."
