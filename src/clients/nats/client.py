import logging

import nats.errors
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy, PubAck, RetentionPolicy, StorageType, StreamConfig

from clients.nats.lifecycle import NatsConnectionErrorPolicy
from settings import NatsSettings

logger = logging.getLogger(__name__)


class NatsJetstreamClient:
    def __init__(self, settings: NatsSettings) -> None:
        self._settings = settings

        self._connection: NATS | None = None
        self._jetstream: JetStreamContext | None = None
        self._error_policy = NatsConnectionErrorPolicy(
            service_name="email-service",
            report_after_attempts=settings.nats_error_report_after_attempts,
        )

    @property
    def is_connected(self) -> bool:
        return self._connection is not None and self._connection.is_connected

    def _get_jetstream(self) -> JetStreamContext:
        if self._jetstream is None or not self.is_connected:
            raise RuntimeError("NATS JetStream client is not connected")

        return self._jetstream

    @property
    def jetstream(self) -> JetStreamContext:
        return self._get_jetstream()

    async def connect(self) -> None:
        if self.is_connected:
            return

        self._connection = NATS()
        self._error_policy.reset()

        await self._connection.connect(
            servers=self._settings.nats_servers,
            name="email-service",
            connect_timeout=5,
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,
            error_cb=self._error_policy.on_error,
            disconnected_cb=self._error_policy.on_disconnected,
            reconnected_cb=self._error_policy.on_reconnected,
            closed_cb=self._error_policy.on_closed,
        )

        self._jetstream = self._connection.jetstream()

    async def close(self) -> None:
        if self._connection is None:
            return

        try:
            if not self._connection.is_closed:
                try:
                    await self._connection.drain()
                except (TimeoutError, nats.errors.Error) as error:
                    logger.warning("NATS drain failed on shutdown, closing connection: %s", error)
                    await self._connection.close()
        finally:
            self._connection = None
            self._jetstream = None

    async def setup(self) -> None:
        """
        Создаёт и актуализирует инфраструктуру JetStream,
        которой владеет основной backend.
        """
        if not self.is_connected:
            raise RuntimeError("NATS client must be connected before setup")

        await self.setup_streams()
        await self.setup_consumers()

    async def setup_streams(self) -> None:
        await self._setup_notification_commands_stream()

    async def _setup_notification_commands_stream(self) -> None:
        jetstream = self._get_jetstream()

        config = StreamConfig(
            name=self._settings.nats_stream_notification_commands,
            subjects=self._settings.nats_subjects_notification_commands,
            storage=StorageType.FILE,
            retention=RetentionPolicy.LIMITS,
        )

        await jetstream.add_stream(config=config)

    async def setup_consumers(self) -> None:
        await self._setup_notification_commans_send_email_consumer()

    async def _setup_notification_commans_send_email_consumer(self) -> None:
        jetstream = self._get_jetstream()

        await jetstream.add_consumer(
            stream=self._settings.nats_stream_notification_commands,
            config=ConsumerConfig(
                durable_name=(self._settings.nats_consumer_notification_commands_send_email),
                filter_subject=(self._settings.nats_subject_notification_commands_send_email),
                deliver_policy=DeliverPolicy.ALL,
                ack_policy=AckPolicy.EXPLICIT,
                ack_wait=(self._settings.nats_consumer_ack_wait_seconds),
                max_deliver=(self._settings.nats_consumer_max_deliver),
            ),
        )

    async def publish(
        self,
        *,
        subject: str,
        payload: bytes,
        headers: dict[str, str] | None = None,
    ) -> PubAck:
        jetstream = self._get_jetstream()

        return await jetstream.publish(
            subject=subject,
            payload=payload,
            headers=headers,
        )
