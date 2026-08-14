import logging
from uuid import UUID

from core.schemas.messaging import NotificationCommandSendEmailData
from core.services.email_processing import EmailProcessingService
from workers.tasks.email import send_email_task

logger = logging.getLogger(__name__)


class NotificationCommandsSendEmailHandler:
    def __init__(
        self,
        *,
        service: EmailProcessingService,
    ) -> None:
        self._service = service

    async def handle(
        self,
        *,
        payload: bytes,
        headers: dict[str, str],
    ) -> None:
        # Валидация входящего сообщения.
        # При ошибке валидации пробрасываем исключение,
        # чтобы consumer сделал message.nak() и сообщение
        # было повторно обработано.
        try:
            event_data = NotificationCommandSendEmailData.model_validate_json(payload)
        except Exception as exc:
            logger.error("Validation failed for incoming NATS message: %s", exc)
            # Попытаемся извлечь event_uuid из payload для логирования
            event_uuid = _try_extract_event_uuid(payload)
            if event_uuid is not None:
                logger.error("Failed event_uuid=%s", event_uuid)
            # Пробрасываем — consumer сделает nak()
            raise

        email_log_id = await self._service.process_incoming_event(
            payload=event_data,
        )

        if email_log_id is None:
            logger.info("Event already processed or failed to create log, acking NATS")
            return

        # Диспатчим в Celery
        send_email_task.delay(str(email_log_id))
        logger.info("Dispatched email_log_id=%s to Celery", email_log_id)


def _try_extract_event_uuid(payload: bytes) -> UUID | None:
    """Best-effort извлечение event_uuid из payload для логирования ошибок."""
    try:
        import json

        data = json.loads(payload)
        raw = data.get("event_uuid")
        if raw is not None:
            return UUID(raw)
    except Exception:
        pass
    return None
