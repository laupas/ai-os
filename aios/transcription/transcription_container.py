from dependency_injector import containers, providers

from aios.transcription.whisper_transcriber import WhisperTranscriber


class TranscriptionContainer(containers.DeclarativeContainer):
    resolver = providers.Dependency()

    transcriber = providers.Singleton(WhisperTranscriber, resolver=resolver)
