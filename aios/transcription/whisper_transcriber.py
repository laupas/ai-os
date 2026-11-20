import aiohttp

from aios.transcription.transcriber import Transcriber
from aios.variables.variable_resolver import VariableResolver

URL = "https://api.openai.com/v1/audio/transcriptions"
KEY = "OPENAI_API_KEY"
LANGUAGE = "AIOS_TRANSCRIBE_LANGUAGE"


class WhisperTranscriber(Transcriber):
    """OpenAI's transcription API, called with plain HTTP. Off without OPENAI_API_KEY.

    The key and the language are Variables set in the console (Settings → General,
    Voice notes), else the environment, and are read for each note: a change
    applies to the next one, without a restart.
    """

    def __init__(self, resolver: VariableResolver | None, model: str = "whisper-1") -> None:
        self._resolver = resolver
        self._model = model

    def is_available(self) -> bool:
        return bool(self._value(KEY))

    async def transcribe(self, audio: bytes, filename: str) -> str:
        form = aiohttp.FormData()
        form.add_field("model", self._model)
        language = self._value(LANGUAGE)
        if language:
            form.add_field("language", language)
        form.add_field("file", audio, filename=filename)
        headers = {"Authorization": f"Bearer {self._value(KEY)}"}
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.post(URL, data=form) as response:
                body = await response.json(content_type=None)
                if response.status >= 300:
                    raise RuntimeError(f"transcription failed: {body}")
                return str(body.get("text", "")).strip()

    def _value(self, name: str) -> str | None:
        return self._resolver.value_of(name) if self._resolver else None
