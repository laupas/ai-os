import json
from typing import Any

from aios.entities.approvals.approval import Approval
from aios.entities.conversations.channel_binding import ChannelBinding

APPROVAL_ACTION_PREFIX = "aios_approval_"
STOP_ACTION = "aios_stop"
_MAX_SECTION = 2900  # Slack rejects section text over 3000 characters


class SlackBlocks:
    """Builds the Block Kit messages ai-os posts and reads their button values."""

    def approval(self, approval: Approval) -> list[dict[str, Any]]:
        buttons = [
            {
                "type": "button",
                "action_id": f"{APPROVAL_ACTION_PREFIX}{index}",
                "text": {"type": "plain_text", "text": option[:75]},
                "value": json.dumps({"approval_id": approval.id, "answer": option}),
                **({"style": "primary"} if index == 0 else {}),
            }
            for index, option in enumerate(approval.options)
        ]
        return [
            self._section(f":raised_hand: {approval.question}"),
            {"type": "actions", "elements": buttons},
        ]

    def answered(self, question: str, answer: str, user_id: str) -> list[dict[str, Any]]:
        return [self._section(f"{question}\n→ *{answer}* (<@{user_id}>)")]

    def status(self, lines: list[str], running: bool) -> list[dict[str, Any]]:
        head = ":hourglass_flowing_sand: Working…" if running else ":white_check_mark: Done"
        blocks: list[dict[str, Any]] = [self._section("\n".join([head, *lines]))]
        if running:
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "action_id": STOP_ACTION,
                            "text": {"type": "plain_text", "text": "Stop"},
                            "style": "danger",
                        }
                    ],
                }
            )
        return blocks

    @staticmethod
    def read_approval_value(value: str) -> tuple[str, str]:
        data = json.loads(value)
        return str(data["approval_id"]), str(data["answer"])

    @staticmethod
    def binding_of(channel_id: str, message: dict[str, Any]) -> ChannelBinding:
        """The conversation a posted message belongs to (its thread, or itself)."""
        thread = message.get("thread_ts") or message["ts"]
        return ChannelBinding(channel="slack", address=channel_id, thread=thread)

    @staticmethod
    def _section(text: str) -> dict[str, Any]:
        return {"type": "section", "text": {"type": "mrkdwn", "text": text[:_MAX_SECTION]}}
