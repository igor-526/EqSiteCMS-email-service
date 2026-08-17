import logging
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.protocols.email_sender import EmailSenderProtocol
from core.schemas.messaging import NotificationCommandSendEmailData
from core.services.email_processing import EmailProcessingService
from repositories.email_log import SQLAlchemyEmailLogRepository
from workers.tasks.email import send_email_task

logger = logging.getLogger(__name__)


class CeleryTaskProtocol(Protocol):
    def delay(self, *args: object, **kwargs: object) -> object: ...


class NotificationCommandsSendEmailHandler:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        email_sender: EmailSenderProtocol,
    ) -> None:
        self._session_factory = session_factory
        self._email_sender = email_sender

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

        async with self._session_factory() as session, session.begin():
            service = EmailProcessingService(
                repository=SQLAlchemyEmailLogRepository(session),
                email_sender=self._email_sender,
            )
            email_log_id = await service.process_incoming_event(payload=event_data)

        if email_log_id is None:
            logger.info("Event already processed or failed to create log, acking NATS")
            return

        # Диспатчим в Celery
        cast(CeleryTaskProtocol, send_email_task).delay(str(email_log_id))
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
