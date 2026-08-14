from dependency_injector import containers, providers

from clients.nats import (
    NatsJetstreamClient,
    NotificationCommandsSendEmailConsumer,
    NotificationCommandsSendEmailHandler,
)
from core.services import NotificationCommandSendEmailService
from settings import nats_settings as nats_settings_instance


class ApplicationContainer(containers.DeclarativeContainer):
    nats_settings = providers.Object(nats_settings_instance)

    nats_client = providers.Singleton(
        NatsJetstreamClient,
        settings=nats_settings,
    )

    notification_command_send_email_service = providers.Singleton(
        NotificationCommandSendEmailService,
    )

    notification_command_send_email_handler = providers.Singleton(
        NotificationCommandsSendEmailHandler,
        service=notification_command_send_email_service,
    )

    notification_command_send_email_consumer = providers.Singleton(
        NotificationCommandsSendEmailConsumer,
        client=nats_client,
        settings=nats_settings,
        handler=notification_command_send_email_handler,
    )
