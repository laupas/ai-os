import asyncio


class RestartRequest:
    """Set from the console to restart ai-os. The web server then stops, which ends
    the process, and docker's restart policy starts it again."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def request(self) -> None:
        self._event.set()

    async def wait(self) -> None:
        await self._event.wait()
