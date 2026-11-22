import logging

from aios.channels.teams.teams_bot import TeamsBot
from aios.channels.teams.teams_cards import TeamsCards
from aios.channels.teams.teams_threads import TeamsThreads
from aios.entities.conversations.channel_binding import ChannelBinding

log = logging.getLogger(__name__)

MAX_LINES = 12


class TeamsStatusTracker:
    """One status card per running turn, edited in place as the agent works, with a
    Stop button while it runs."""

    def __init__(self, bot: TeamsBot, cards: TeamsCards, threads: TeamsThreads) -> None:
        self._bot = bot
        self._cards = cards
        self._threads = threads
        self._messages: dict[tuple[str, str], tuple[str, list[str]]] = {}

    async def add(self, binding: ChannelBinding, service_url: str, line: str) -> None:
        key = (binding.address, binding.thread)
        activity_id, lines = self._messages.get(key, ("", []))
        if lines and lines[-1] == f"· {line}":
            return
        lines = [*lines, f"· {line}"][-MAX_LINES:]
        card = self._cards.status(lines, running=True)
        conversation_id = TeamsThreads.conversation_id(binding)
        try:
            if activity_id:
                await self._bot.update_card(
                    service_url, conversation_id, activity_id, card, "Working…"
                )
            else:
                activity_id = await self._bot.send_card(
                    service_url,
                    conversation_id,
                    card,
                    "Working…",
                    self._threads.reply_chain(binding),
                )
                self._threads.remember(activity_id, binding)
        except Exception as exc:
            log.warning("status update failed: %s", exc)
        self._messages[key] = (activity_id, lines)

    async def finish(self, binding: ChannelBinding, service_url: str) -> None:
        activity_id, lines = self._messages.pop((binding.address, binding.thread), ("", []))
        if not activity_id:
            return
        try:
            await self._bot.update_card(
                service_url,
                TeamsThreads.conversation_id(binding),
                activity_id,
                self._cards.status(lines, running=False),
                "Done",
            )
        except Exception as exc:
            log.warning("status update failed: %s", exc)
