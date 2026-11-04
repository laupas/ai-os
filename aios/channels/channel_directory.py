from collections.abc import Callable

from aios.approvals.approval_presenter import ApprovalPresenter
from aios.approvals.approval_presenter_resolver import ApprovalPresenterResolver
from aios.approvals.text_approval_presenter import TextApprovalPresenter
from aios.channels.message_channel import MessageChannel
from aios.channels.thread_starter import ThreadStarter
from aios.progress.null_progress_reporter import NullProgressReporter
from aios.progress.progress_reporter import ProgressReporter
from aios.progress.progress_reporter_resolver import ProgressReporterResolver


class ChannelDirectory(ApprovalPresenterResolver, ProgressReporterResolver):
    """The enabled channels, created on first use, plus their optional extras."""

    def __init__(
        self, factories: dict[str, Callable[[], MessageChannel]], enabled: list[str]
    ) -> None:
        unknown = set(enabled) - set(factories)
        if unknown:
            raise ValueError(f"unknown channels in config: {sorted(unknown)}")
        self._factories = factories
        self._enabled = list(enabled)
        self._channels: dict[str, MessageChannel] = {}

    def enabled(self) -> list[MessageChannel]:
        return [self.get(name) for name in self._enabled]

    def get(self, name: str) -> MessageChannel:
        if name not in self._enabled:
            raise KeyError(f"channel {name!r} is not enabled")
        if name not in self._channels:
            self._channels[name] = self._factories[name]()
        return self._channels[name]

    def presenter_for(self, channel: str) -> ApprovalPresenter:
        instance = self.get(channel)
        if isinstance(instance, ApprovalPresenter):
            return instance
        return TextApprovalPresenter(instance)

    def reporter_for(self, channel: str) -> ProgressReporter:
        instance = self.get(channel)
        if isinstance(instance, ProgressReporter):
            return instance
        return NullProgressReporter()

    def thread_starter_for(self, channel: str) -> ThreadStarter | None:
        instance = self.get(channel)
        return instance if isinstance(instance, ThreadStarter) else None
