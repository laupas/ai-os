from dependency_injector import containers, providers

from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_catalog import ChannelCatalog
from aios.channels.channel_directory import ChannelDirectory
from aios.channels.channel_values import ChannelValues
from aios.channels.slack.slack_channel_type import SlackChannelType
from aios.channels.teams.teams_channel_type import TeamsChannelType
from aios.channels.web.web_channel import WebChannel
from aios.channels.web.web_channel_type import WebChannelType
from aios.channels.web.web_event_hub import WebEventHub
from aios.messaging.mail.mail_channel_type import MailChannelType
from aios.messaging.sender_directory import SenderDirectory
from aios.messaging.signal.signal_channel_type import SignalChannelType
from aios.messaging.webhook.webhook_channel_type import WebhookChannelType
from aios.messaging.webhook.webhook_poster import WebhookPoster
from aios.messaging.webhook.webhook_template import WebhookTemplate


class ChannelsContainer(containers.DeclarativeContainer):
    """Every channel ai-os can use, chatting or sending. A new channel is one
    `ChannelType` plus one entry in `types`. Channels are only created when on, so
    one that is off needs no tokens."""

    config = providers.Dependency()
    resolver = providers.Dependency()
    transcriber = providers.Dependency()
    voice_gate = providers.Dependency()
    ids = providers.Dependency()

    # Both are used by the web server: the hub observes every conversation, and the
    # server needs this very channel instance.
    web_hub = providers.Singleton(WebEventHub)
    web = providers.Singleton(WebChannel, ids=ids)

    types = providers.List(
        providers.Singleton(SlackChannelType, transcriber=transcriber, voice_gate=voice_gate),
        providers.Singleton(WebChannelType, channel=web),
        providers.Singleton(SignalChannelType),
        providers.Singleton(MailChannelType),
        providers.Singleton(TeamsChannelType, transcriber=transcriber, voice_gate=voice_gate),
        providers.Singleton(WebhookChannelType),
    )
    values = providers.Singleton(ChannelValues, resolver=resolver)
    catalog = providers.Singleton(ChannelCatalog, types=types, config=config, values=values)

    directory = providers.Singleton(
        ChannelDirectory,
        factories=catalog.provided.channel_factories.call(),
        enabled=catalog.provided.enabled.call(ChannelCapability.CHAT),
    )
    senders = providers.Singleton(
        SenderDirectory,
        factories=catalog.provided.sender_factories.call(),
        enabled=catalog.provided.enabled.call(ChannelCapability.SEND),
    )
    webhook_poster = providers.Singleton(
        WebhookPoster,
        template=providers.Singleton(WebhookTemplate, resolver=resolver),
        enabled=catalog.provided.is_on.call("webhook"),
    )
