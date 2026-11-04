from dependency_injector import containers, providers

from aios.messaging.mail.mail_over_resend_sender import MailOverResendSender
from aios.messaging.sender_directory import SenderDirectory
from aios.messaging.signal.signal_sender import SignalSender


class MessagingContainer(containers.DeclarativeContainer):
    """A new sender is one provider here plus one entry in `directory`."""

    settings = providers.Dependency()
    enabled = providers.Dependency()

    signal = providers.Singleton(
        SignalSender,
        api_url=settings.provided.signal_api_url,
        sender_number=settings.provided.signal_sender,
    )
    mail = providers.Singleton(
        MailOverResendSender,
        api_key=settings.provided.resend_api_key,
        mail_from=settings.provided.mail_from,
    )

    directory = providers.Singleton(
        SenderDirectory,
        factories=providers.Dict(signal=signal.provider, mail=mail.provider),
        enabled=enabled,
    )
