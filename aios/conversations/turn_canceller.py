import asyncio


class TurnCanceller:
    """Remembers the running turn of each conversation so it can be stopped."""

    def __init__(self) -> None:
        self._running: dict[str, asyncio.Task[None]] = {}

    def track(self, conversation_id: str, task: asyncio.Task[None]) -> None:
        self._running[conversation_id] = task

    def forget(self, conversation_id: str) -> None:
        self._running.pop(conversation_id, None)

    def cancel(self, conversation_id: str) -> bool:
        task = self._running.get(conversation_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True
