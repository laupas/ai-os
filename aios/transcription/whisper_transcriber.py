import aiohttp

from aios.transcription.transcriber import Transcriber

URL = "https://api.openai.com/v1/audio/transcriptions"


class WhisperTranscriber(Transcriber):
    """OpenAI's transcription API, called with plain HTTP. Off without OPENAI_API_KEY."""

    def __init__(self, api_key: str | None, language: str | None, model: str = "whisper-1") -> None:
        self._api_key = api_key
        self._language = language
        self._model = model

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def transcribe(self, audio: bytes, filename: str) -> str:
        form = aiohttp.FormData()
        form.add_field("model", self._model)
        if self._language:
            form.add_field("language", self._language)
        form.add_field("file", audio, filename=filename)
        headers = {"Authorization": f"Bearer {self._api_key}"}
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.post(URL, data=form) as response:
                body = await response.json(content_type=None)
                if response.status >= 300:
                    raise RuntimeError(f"transcription failed: {body}")
                return str(body.get("text", "")).strip()
