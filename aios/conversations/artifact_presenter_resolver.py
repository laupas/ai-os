from abc import ABC, abstractmethod

from aios.conversations.artifact_presenter import ArtifactPresenter


class ArtifactPresenterResolver(ABC):
    @abstractmethod
    def artifact_presenter_for(self, channel: str) -> ArtifactPresenter: ...
