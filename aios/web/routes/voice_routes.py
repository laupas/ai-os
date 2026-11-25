import logging

from aiohttp import web

from aios.entities.users.permission import Permission
from aios.transcription.transcriber import Transcriber
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes

log = logging.getLogger(__name__)

# Two minutes of 16 kHz WAV, the largest recording the console sends, is about 4 MB;
# the rest of the API keeps the server's 1 MB limit.
MAX_AUDIO_BYTES = 10 * 1024**2

# The transcription API tells formats apart by the file name.
EXTENSIONS = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "audio/x-m4a": "m4a",
    "audio/aac": "aac",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
}


class VoiceRoutes(WebRoutes):
    """Speech into text for talking with ai-os instead of typing.

    The browser records what was said and posts it as the raw request body; the
    transcript comes back, and the browser sends it as a chat message marked as
    voice. Speaking the reply is left to the device. Transcribing costs, so it
    takes the `voice` permission.
    """

    def __init__(self, transcriber: Transcriber, max_bytes: int = MAX_AUDIO_BYTES) -> None:
        self._transcriber = transcriber
        self._max_bytes = max_bytes

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/voice", self._status)
        app.router.add_post("/api/voice/transcriptions", self._transcribe)

    async def _status(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.VOICE)
        return web.json_response({"available": self._transcriber.is_available()})

    async def _transcribe(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.VOICE)
        if not self._transcriber.is_available():
            raise web.HTTPServiceUnavailable(text="transcription is not set up (OPENAI_API_KEY)")
        extension = EXTENSIONS.get(request.content_type)
        if extension is None:
            raise web.HTTPUnsupportedMediaType(
                text=f"not a known audio type: {request.content_type}"
            )
        audio = await self._audio(request)
        if not audio:
            raise web.HTTPBadRequest(text="no audio")
        try:
            text = await self._transcriber.transcribe(audio, f"speech.{extension}")
        except Exception as exc:
            log.warning("transcription failed: %s", exc)
            raise web.HTTPBadGateway(text="transcription failed") from exc
        return web.json_response({"text": text})

    async def _audio(self, request: web.Request) -> bytes:
        """The body, read past the server-wide limit up to this route's own."""
        audio = bytearray()
        async for chunk in request.content.iter_chunked(64 * 1024):
            audio += chunk
            if len(audio) > self._max_bytes:
                raise web.HTTPRequestEntityTooLarge(
                    max_size=self._max_bytes, actual_size=len(audio)
                )
        return bytes(audio)
