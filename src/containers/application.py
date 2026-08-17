from dependency_injector import containers, providers

from clients.nats import (
    NatsJetstreamClient,
    NotificationCommandsSendEmailConsumer,
    NotificationCommandsSendEmailHandler,
)
from core.services import NotificationCommandSendEmailService
from infrastructure.email_sender import SMTPEmailSender
from settings import celery_settings as celery_settings_instance
from settings import nats_settings as nats_settings_instance
from settings import smtp_settings as smtp_settings_instance
from utils.database import SessionFactory


class ApplicationContainer(containers.DeclarativeContainer):
    nats_settings = providers.Object(nats_settings_instance)
    smtp_settings = providers.Object(smtp_settings_instance)

    nats_client = providers.Singleton(
        NatsJetstreamClient,
        settings=nats_settings,
    )

    # Infrastructure
    email_sender = providers.Singleton(SMTPEmailSender)

    notification_command_send_email_service = providers.Singleton(
        NotificationCommandSendEmailService,
    )

    notification_command_send_email_handler = providers.Singleton(
        NotificationCommandsSendEmailHandler,
        session_factory=providers.Object(SessionFactory),
        email_sender=email_sender,
    )

    notification_command_send_email_consumer = providers.Singleton(
        NotificationCommandsSendEmailConsumer,
        client=nats_client,
        settings=nats_settings,
        handler=notification_command_send_email_handler,
    )

    # Celery
    celery_settings = providers.Object(celery_settings_instance)
    celery_app = providers.Singleton(
        lambda: __import__("workers.celery_app", fromlist=["celery_app"]).celery_app,
    )
