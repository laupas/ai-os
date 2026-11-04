from abc import ABC, abstractmethod


class Transcriber(ABC):
    """Turns recorded speech into text."""

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    async def transcribe(self, audio: bytes, filename: str) -> str: ...
