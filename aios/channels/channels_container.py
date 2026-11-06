from dependency_injector import containers, providers

from aios.channels.channel_directory import ChannelDirectory
from aios.channels.slack.markdown_to_mrkdwn import MarkdownToMrkdwn
from aios.channels.slack.message_chunker import MessageChunker
from aios.channels.slack.slack_blocks import SlackBlocks
from aios.channels.slack.slack_channel import SlackChannel
from aios.channels.slack.slack_voice_notes import SlackVoiceNotes
from aios.channels.web.web_channel import WebChannel
from aios.channels.web.web_event_hub import WebEventHub


class ChannelsContainer(containers.DeclarativeContainer):
    """A new channel is one provider here plus one entry in `directory`.
    Channels are only created when enabled, so a disabled one needs no tokens."""

    settings = providers.Dependency()
    enabled = providers.Dependency()
    transcriber = providers.Dependency()
    ids = providers.Dependency()

    slack = providers.Singleton(
        SlackChannel,
        bot_token=settings.provided.slack_bot_token,
        app_token=settings.provided.slack_app_token,
        blocks=providers.Singleton(SlackBlocks),
        converter=providers.Singleton(MarkdownToMrkdwn),
        chunker=providers.Singleton(MessageChunker, size=3500),
        voice_notes=providers.Singleton(
            SlackVoiceNotes, bot_token=settings.provided.slack_bot_token, transcriber=transcriber
        ),
    )

    # Both are used by the web server: the hub observes every conversation, and the
    # server needs this very channel instance.
    web_hub = providers.Singleton(WebEventHub)
    web = providers.Singleton(WebChannel, ids=ids)

    directory = providers.Singleton(
        ChannelDirectory,
        factories=providers.Dict(slack=slack.provider, web=web.provider),
        enabled=enabled,
    )
