from aios.entities.conversations.channel_binding import ChannelBinding
from aios.progress.progress_event import ProgressEvent
from aios.progress.progress_reporter import ProgressReporter


class NullProgressReporter(ProgressReporter):
    """Used for channels that cannot show progress."""

    async def report(self, binding: ChannelBinding, event: ProgressEvent) -> None:
        return None

    async def finish(self, binding: ChannelBinding) -> None:
        return None
