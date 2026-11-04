from abc import ABC, abstractmethod

from aios.progress.progress_reporter import ProgressReporter


class ProgressReporterResolver(ABC):
    @abstractmethod
    def reporter_for(self, channel: str) -> ProgressReporter: ...
