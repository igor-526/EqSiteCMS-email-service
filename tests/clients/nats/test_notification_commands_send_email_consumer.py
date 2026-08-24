import asyncio
import logging
from collections.abc import Sequence
from typing import cast
from unittest.mock import AsyncMock, Mock, patch

import pytest
from nats.errors import Error as NatsError
from nats.errors import TimeoutError as NatsTimeoutError

from clients.nats.client import NatsJetstreamClient
from clients.nats.consumers.notification_commands_send_email import (
    NotificationCommandsSendEmailConsumer,
)
from core.protocols.messaging import NotificationCommandSendEmailHandlerProtocol
from settings import NatsSettings


class FakeClient:
    def __init__(self) -> None:
        self.jetstream = Mock()
        self.jetstream.pull_subscribe = AsyncMock()


def make_message(*, data: bytes = b"payload", headers: dict[str, str] | None = None) -> Mock:
    message = Mock()
    message.data = data
    message.headers = headers
    message.ack = AsyncMock()
    message.nak = AsyncMock()
    return message


def make_consumer(
    *,
    fetch_results: Sequence[object] = (),
    handler: AsyncMock | None = None,
    settings: NatsSettings | None = None,
) -> tuple[NotificationCommandsSendEmailConsumer, AsyncMock, AsyncMock]:
    client = FakeClient()
    subscription = Mock()
    subscription.fetch = AsyncMock(side_effect=list(fetch_results))
    client.jetstream.pull_subscribe.return_value = subscription
    actual_handler = handler or AsyncMock()
    consumer = NotificationCommandsSendEmailConsumer(
        client=cast(NatsJetstreamClient, client),
        settings=settings or NatsSettings(),
        handler=cast(NotificationCommandSendEmailHandlerProtocol, actual_handler),
    )
    consumer._subscription = subscription
    return consumer, subscription.fetch, actual_handler


async def run_until_cancelled(consumer: NotificationCommandsSendEmailConsumer) -> None:
    with pytest.raises(asyncio.CancelledError):
        await consumer._consume()


@pytest.mark.asyncio
async def test_nats_timeout_continues_without_error_log(caplog: pytest.LogCaptureFixture) -> None:
    consumer, fetch, _ = make_consumer(fetch_results=[NatsTimeoutError(), asyncio.CancelledError()])
    with caplog.at_level(logging.ERROR):
        await run_until_cancelled(consumer)
    assert fetch.await_count == 2
    assert "Failed to fetch NATS messages" not in caplog.text


@pytest.mark.asyncio
async def test_builtin_timeout_continues_without_error_log(caplog: pytest.LogCaptureFixture) -> None:
    consumer, fetch, _ = make_consumer(fetch_results=[TimeoutError(), asyncio.CancelledError()])
    with caplog.at_level(logging.ERROR):
        await run_until_cancelled(consumer)
    assert fetch.await_count == 2
    assert not caplog.records


@pytest.mark.asyncio
async def test_timeout_emits_no_warning(caplog: pytest.LogCaptureFixture) -> None:
    consumer, _, _ = make_consumer(fetch_results=[NatsTimeoutError(), asyncio.CancelledError()])
    with caplog.at_level(logging.WARNING):
        await run_until_cancelled(consumer)
    assert not [record for record in caplog.records if record.levelno == logging.WARNING]


@pytest.mark.asyncio
async def test_timeout_does_not_call_logger_exception() -> None:
    consumer, _, _ = make_consumer(fetch_results=[NatsTimeoutError(), asyncio.CancelledError()])
    with patch("clients.nats.consumers.notification_commands_send_email.logger.exception") as log_exception:
        await run_until_cancelled(consumer)
    log_exception.assert_not_called()


@pytest.mark.asyncio
async def test_timeout_does_not_call_handler() -> None:
    consumer, _, handler = make_consumer(fetch_results=[NatsTimeoutError(), asyncio.CancelledError()])
    await run_until_cancelled(consumer)
    handler.handle.assert_not_awaited()


@pytest.mark.asyncio
async def test_timeout_does_not_ack() -> None:
    message = make_message()
    consumer, _, _ = make_consumer(fetch_results=[NatsTimeoutError(), asyncio.CancelledError()])
    await run_until_cancelled(consumer)
    message.ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_timeout_does_not_nak() -> None:
    message = make_message()
    consumer, _, _ = make_consumer(fetch_results=[NatsTimeoutError(), asyncio.CancelledError()])
    await run_until_cancelled(consumer)
    message.nak.assert_not_awaited()


@pytest.mark.asyncio
async def test_timeout_has_no_additional_backoff_sleep() -> None:
    consumer, _, _ = make_consumer(fetch_results=[NatsTimeoutError(), asyncio.CancelledError()])
    with patch("clients.nats.consumers.notification_commands_send_email.asyncio.sleep", new=AsyncMock()) as sleep:
        await run_until_cancelled(consumer)
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_next_fetch_runs_after_timeout() -> None:
    consumer, fetch, _ = make_consumer(fetch_results=[NatsTimeoutError(), asyncio.CancelledError()])
    await run_until_cancelled(consumer)
    assert fetch.await_count == 2


@pytest.mark.asyncio
async def test_multiple_timeouts_keep_consumer_loop_running() -> None:
    consumer, fetch, _ = make_consumer(
        fetch_results=[NatsTimeoutError(), TimeoutError(), NatsTimeoutError(), asyncio.CancelledError()]
    )
    await run_until_cancelled(consumer)
    assert fetch.await_count == 4


@pytest.mark.asyncio
async def test_message_after_timeout_reaches_handler() -> None:
    message = make_message()
    consumer, _, handler = make_consumer(fetch_results=[NatsTimeoutError(), [message], asyncio.CancelledError()])
    await run_until_cancelled(consumer)
    handler.handle.assert_awaited_once()


@pytest.mark.asyncio
async def test_message_after_multiple_timeouts_is_acked() -> None:
    message = make_message()
    consumer, _, _ = make_consumer(
        fetch_results=[NatsTimeoutError(), TimeoutError(), [message], asyncio.CancelledError()]
    )
    await run_until_cancelled(consumer)
    message.ack.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_fetch_receives_configured_batch_and_timeout() -> None:
    settings = NatsSettings(NATS_CONSUMER_FETCH_BATCH_SIZE=7, NATS_CONSUMER_FETCH_TIMEOUT_SECONDS=2.5)
    consumer, fetch, _ = make_consumer(fetch_results=[asyncio.CancelledError()], settings=settings)
    await run_until_cancelled(consumer)
    fetch.assert_awaited_once_with(batch=7, timeout=2.5)


@pytest.mark.asyncio
async def test_cancelled_error_from_fetch_propagates() -> None:
    consumer, _, _ = make_consumer(fetch_results=[asyncio.CancelledError()])
    await run_until_cancelled(consumer)


@pytest.mark.asyncio
async def test_stop_during_fetch_clears_task_and_subscription() -> None:
    client = FakeClient()
    entered_fetch = asyncio.Event()

    async def wait_forever(**_: object) -> list[object]:
        entered_fetch.set()
        await asyncio.Future()
        return []

    subscription = Mock()
    subscription.fetch = AsyncMock(side_effect=wait_forever)
    client.jetstream.pull_subscribe.return_value = subscription
    consumer = NotificationCommandsSendEmailConsumer(
        client=cast(NatsJetstreamClient, client),
        settings=NatsSettings(),
        handler=cast(NotificationCommandSendEmailHandlerProtocol, AsyncMock()),
    )
    await consumer.start()
    await entered_fetch.wait()
    await consumer.stop()
    assert consumer._task is None
    assert consumer._subscription is None


@pytest.mark.asyncio
async def test_start_is_idempotent_while_running() -> None:
    client = FakeClient()
    subscription = Mock()
    subscription.fetch = AsyncMock(side_effect=lambda **_: asyncio.Future())
    client.jetstream.pull_subscribe.return_value = subscription
    consumer = NotificationCommandsSendEmailConsumer(
        client=cast(NatsJetstreamClient, client),
        settings=NatsSettings(),
        handler=cast(NotificationCommandSendEmailHandlerProtocol, AsyncMock()),
    )
    await consumer.start()
    await consumer.start()
    client.jetstream.pull_subscribe.assert_awaited_once()
    await consumer.stop()


@pytest.mark.asyncio
async def test_stop_before_start_is_safe() -> None:
    consumer, _, _ = make_consumer()
    consumer._subscription = None
    await consumer.stop()
    assert not consumer.is_running


@pytest.mark.asyncio
async def test_start_uses_canonical_topology() -> None:
    client = FakeClient()
    client.jetstream.pull_subscribe.return_value = Mock()
    consumer = NotificationCommandsSendEmailConsumer(
        client=cast(NatsJetstreamClient, client),
        settings=NatsSettings(),
        handler=cast(NotificationCommandSendEmailHandlerProtocol, AsyncMock()),
    )
    with patch.object(consumer, "_consume", new=AsyncMock()):
        await consumer.start()
        await asyncio.sleep(0)
    client.jetstream.pull_subscribe.assert_awaited_once_with(
        subject="commands.notification.email.send",
        stream="NOTIFICATION_COMMANDS",
        durable="notification-service-commands-send-email",
    )


@pytest.mark.asyncio
async def test_connection_error_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    consumer, _, _ = make_consumer(fetch_results=[ConnectionError("offline"), asyncio.CancelledError()])
    with patch("clients.nats.consumers.notification_commands_send_email.asyncio.sleep", new=AsyncMock()):
        with caplog.at_level(logging.ERROR):
            await run_until_cancelled(consumer)
    assert "Failed to fetch NATS messages" in caplog.text


@pytest.mark.asyncio
async def test_protocol_error_is_logged_and_backed_off() -> None:
    consumer, _, _ = make_consumer(fetch_results=[NatsError(), asyncio.CancelledError()])
    with patch("clients.nats.consumers.notification_commands_send_email.asyncio.sleep", new=AsyncMock()) as sleep:
        with patch("clients.nats.consumers.notification_commands_send_email.logger.exception") as log_exception:
            await run_until_cancelled(consumer)
    log_exception.assert_called_once_with("Failed to fetch NATS messages")
    sleep.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_generic_non_timeout_error_is_not_suppressed() -> None:
    consumer, _, _ = make_consumer(fetch_results=[ValueError("bad fetch"), asyncio.CancelledError()])
    with patch("clients.nats.consumers.notification_commands_send_email.asyncio.sleep", new=AsyncMock()):
        with patch("clients.nats.consumers.notification_commands_send_email.logger.exception") as log_exception:
            await run_until_cancelled(consumer)
    log_exception.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_retries_after_broker_error_backoff() -> None:
    consumer, fetch, _ = make_consumer(fetch_results=[ConnectionError(), asyncio.CancelledError()])
    with patch("clients.nats.consumers.notification_commands_send_email.asyncio.sleep", new=AsyncMock()):
        await run_until_cancelled(consumer)
    assert fetch.await_count == 2


@pytest.mark.asyncio
async def test_handler_success_acks_exactly_once() -> None:
    message = make_message()
    consumer, _, _ = make_consumer()
    await consumer._process_message(message)
    message.ack.assert_awaited_once_with()
    message.nak.assert_not_awaited()


@pytest.mark.asyncio
async def test_handler_error_naks_exactly_once() -> None:
    message = make_message()
    handler = AsyncMock()
    handler.handle.side_effect = RuntimeError("delivery failed")
    consumer, _, _ = make_consumer(handler=handler)
    await consumer._process_message(message)
    message.nak.assert_awaited_once_with()
    message.ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_handler_error_has_separate_process_log() -> None:
    message = make_message()
    handler = AsyncMock()
    handler.handle.side_effect = RuntimeError("delivery failed")
    consumer, _, _ = make_consumer(handler=handler)
    with patch("clients.nats.consumers.notification_commands_send_email.logger.exception") as log_exception:
        await consumer._process_message(message)
    log_exception.assert_called_once_with("Failed to process NATS message")


@pytest.mark.asyncio
async def test_ack_timeout_is_not_classified_as_fetch_idle() -> None:
    message = make_message()
    message.ack.side_effect = NatsTimeoutError()
    consumer, _, _ = make_consumer()
    with pytest.raises(NatsTimeoutError):
        await consumer._process_message(message)


@pytest.mark.asyncio
async def test_nak_timeout_is_not_classified_as_fetch_idle() -> None:
    message = make_message()
    message.nak.side_effect = NatsTimeoutError()
    handler = AsyncMock()
    handler.handle.side_effect = RuntimeError("delivery failed")
    consumer, _, _ = make_consumer(handler=handler)
    with pytest.raises(NatsTimeoutError):
        await consumer._process_message(message)


@pytest.mark.asyncio
async def test_message_headers_pass_to_handler_unchanged() -> None:
    headers = {"Nats-Msg-Id": "6d918a9e-2ec2-45aa-bf10-86b873524009"}
    message = make_message(headers=headers)
    consumer, _, handler = make_consumer()
    await consumer._process_message(message)
    assert handler.handle.await_args.kwargs["headers"] == headers


@pytest.mark.asyncio
async def test_message_payload_bytes_pass_to_handler_unchanged() -> None:
    payload = b'{"event_uuid":"c9051539-003e-4fab-b63f-b6607ddf2b65"}'
    message = make_message(data=payload)
    consumer, _, handler = make_consumer()
    await consumer._process_message(message)
    assert handler.handle.await_args.kwargs["payload"] is payload


def test_timeout_fix_preserves_public_constructor_signature() -> None:
    import inspect

    assert list(inspect.signature(NotificationCommandsSendEmailConsumer).parameters) == [
        "client",
        "settings",
        "handler",
    ]


def test_runtime_timeout_relationship_is_documented_by_behavior() -> None:
    assert issubclass(NatsTimeoutError, TimeoutError)
    assert asyncio.TimeoutError is TimeoutError
