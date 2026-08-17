from typing import cast
from unittest.mock import AsyncMock

import pytest

from clients.nats.client import NatsJetstreamClient
from clients.nats.consumers.notification_commands_send_email import (
    NotificationCommandsSendEmailConsumer,
)
from core.protocols.messaging import NotificationCommandSendEmailHandlerProtocol
from settings import NatsSettings


class RecordingNatsClient:
    def __init__(self) -> None:
        self.jetstream = AsyncMock()


class ContractEmailConsumer(NotificationCommandsSendEmailConsumer):
    async def _consume(self) -> None:
        return None


@pytest.mark.asyncio
async def test_email_consumer_uses_canonical_subject_stream_and_durable() -> None:
    client = RecordingNatsClient()
    client.jetstream.pull_subscribe.return_value = AsyncMock()
    consumer = ContractEmailConsumer(
        client=cast(NatsJetstreamClient, client),
        settings=NatsSettings(),
        handler=cast(NotificationCommandSendEmailHandlerProtocol, AsyncMock()),
    )

    await consumer.start()

    client.jetstream.pull_subscribe.assert_awaited_once_with(
        subject="commands.notification.email.send",
        durable="notification-service-commands-send-email",
        stream="NOTIFICATION_COMMANDS",
    )
