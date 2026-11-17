from aios.transcription.transcriber import Transcriber


class FakeTranscriber(Transcriber):
    """Answers every recording with a fixed transcript and keeps what it was given."""

    def __init__(self, text: str = "hello by voice", available: bool = True) -> None:
        self._text = text
        self._available = available
        self.calls: list[tuple[bytes, str]] = []

    def is_available(self) -> bool:
        return self._available

    async def transcribe(self, audio: bytes, filename: str) -> str:
        self.calls.append((audio, filename))
        return self._text
