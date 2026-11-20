from typing import Any

from aios.entities.approvals.approval import Approval

ACTION = "aios"
APPROVAL = "approval"
STOP = "stop"


class TeamsCards:
    """Builds the Adaptive Cards ai-os posts. A button press comes back as a message
    activity whose `value` is the button's data, marked with `aios`."""

    def approval(self, approval: Approval) -> dict[str, Any]:
        actions = [
            {
                "type": "Action.Submit",
                "title": option[:75],
                "data": {
                    ACTION: APPROVAL,
                    "approval_id": approval.id,
                    "answer": option,
                    "question": approval.question,
                },
                **({"style": "positive"} if index == 0 else {}),
            }
            for index, option in enumerate(approval.options)
        ]
        return self._card([self._text(f"✋ {approval.question}")], actions)

    def answered(self, question: str, answer: str, by: str) -> dict[str, Any]:
        return self._card([self._text(question), self._text(f"→ **{answer}** ({by})")], [])

    def status(self, lines: list[str], running: bool) -> dict[str, Any]:
        head = "⏳ Working…" if running else "✅ Done"
        body = [self._text(head, bold=True), *(self._text(line) for line in lines)]
        stop = {
            "type": "Action.Submit",
            "title": "Stop",
            "style": "destructive",
            "data": {ACTION: STOP},
        }
        return self._card(body, [stop] if running else [])

    @staticmethod
    def read_action(value: Any) -> dict[str, Any] | None:
        """The data of an ai-os button, or None for anything else."""
        if isinstance(value, dict) and value.get(ACTION) in {APPROVAL, STOP}:
            return value
        return None

    @staticmethod
    def _card(body: list[dict[str, Any]], actions: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4",
            "body": body,
            "actions": actions,
        }

    @staticmethod
    def _text(text: str, bold: bool = False) -> dict[str, Any]:
        block: dict[str, Any] = {"type": "TextBlock", "text": text, "wrap": True}
        if bold:
            block["weight"] = "Bolder"
        return block
