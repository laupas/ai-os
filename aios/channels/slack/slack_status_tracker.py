import logging

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from aios.channels.slack.slack_blocks import SlackBlocks
from aios.entities.conversations.channel_binding import ChannelBinding

log = logging.getLogger(__name__)

MAX_LINES = 12


class SlackStatusTracker:
    """One status message per running turn, edited in place as the agent works,
    with a Stop button while it runs."""

    def __init__(self, client: AsyncWebClient, blocks: SlackBlocks) -> None:
        self._client = client
        self._blocks = blocks
        self._messages: dict[tuple[str, str], tuple[str, list[str]]] = {}

    async def add(self, binding: ChannelBinding, line: str) -> None:
        key = (binding.address, binding.thread)
        ts, lines = self._messages.get(key, ("", []))
        if lines and lines[-1] == f"· {line}":
            return
        lines = [*lines, f"· {line}"][-MAX_LINES:]
        blocks = self._blocks.status(lines, running=True)
        try:
            if ts:
                await self._client.chat_update(
                    channel=binding.address, ts=ts, text="Working…", blocks=blocks
                )
            else:
                response = await self._client.chat_postMessage(
                    channel=binding.address,
                    thread_ts=binding.thread,
                    text="Working…",
                    blocks=blocks,
                )
                ts = str(response["ts"])
        except SlackApiError as exc:
            log.warning("status update failed: %s", exc)
        self._messages[key] = (ts, lines)

    async def finish(self, binding: ChannelBinding) -> None:
        ts, lines = self._messages.pop((binding.address, binding.thread), ("", []))
        if not ts:
            return
        try:
            await self._client.chat_update(
                channel=binding.address,
                ts=ts,
                text="Done",
                blocks=self._blocks.status(lines, running=False),
            )
        except SlackApiError as exc:
            log.warning("status update failed: %s", exc)
