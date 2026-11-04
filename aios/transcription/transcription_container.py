from dependency_injector import containers, providers

from aios.transcription.whisper_transcriber import WhisperTranscriber


class TranscriptionContainer(containers.DeclarativeContainer):
    settings = providers.Dependency()

    transcriber = providers.Singleton(
        WhisperTranscriber,
        api_key=settings.provided.openai_api_key,
        language=settings.provided.transcribe_language,
    )
