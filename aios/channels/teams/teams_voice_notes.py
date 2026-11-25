import logging

import aiohttp

from aios.conversations.attachment import Attachment
from aios.conversations.inbound_message import InboundMessage
from aios.transcription.transcriber import Transcriber
from aios.users.voice_gate import VoiceGate

log = logging.getLogger(__name__)

AUDIO_EXTENSIONS = (".m4a", ".mp3", ".mp4", ".ogg", ".oga", ".wav", ".webm", ".aac", ".flac")


class TeamsVoiceNotes:
    """Replaces an audio file sent in a Teams chat with its transcript. Teams hands
    the bot a download link that is already signed, so no token goes with it. Only
    for senders the gate lets through."""

    def __init__(self, transcriber: Transcriber, gate: VoiceGate) -> None:
        self._transcriber = transcriber
        self._gate = gate

    def allowed(self, message: InboundMessage) -> bool:
        """Whether its sender may have a voice note transcribed (`VoiceGate`)."""
        return self._gate.allows(message.sender)

    def may_be_told(self, message: InboundMessage) -> bool:
        """Whether to tell the sender why their voice note was not listened to."""
        return self._gate.may_be_told(message.sender)

    def audio_in(self, message: InboundMessage) -> Attachment | None:
        return next(
            (a for a in message.attachments if a.name.lower().endswith(AUDIO_EXTENSIONS)), None
        )

    async def transcribe(self, message: InboundMessage) -> tuple[InboundMessage, str | None]:
        """Returns the message with the transcript as text, and the transcript."""
        audio = self.audio_in(message)
        if audio is None or audio.url is None or not self._transcriber.is_available():
            return message, None
        async with aiohttp.ClientSession() as session:
            async with session.get(audio.url) as response:
                response.raise_for_status()
                data = await response.read()
        transcript = await self._transcriber.transcribe(data, audio.name)
        text = f"{message.text}\n{transcript}".strip()
        return message.model_copy(update={"text": text}), transcript
