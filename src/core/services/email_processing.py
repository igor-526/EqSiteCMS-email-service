import logging
from uuid import UUID

from core.protocols.email_sender import EmailSenderProtocol
from core.schemas.messaging import NotificationCommandSendEmailData
from repositories.protocols import EmailLogRepositoryProtocol

logger = logging.getLogger(__name__)


class EmailProcessingService:
    def __init__(
        self,
        *,
        repository: EmailLogRepositoryProtocol,
        email_sender: EmailSenderProtocol,
    ) -> None:
        self._repository = repository
        self._email_sender = email_sender

    async def process_incoming_event(
        self,
        *,
        payload: NotificationCommandSendEmailData,
    ) -> UUID | None:
        """
        Обработка входящего NATS-события.

        1. Попытка вставить запись с event_uuid (идемпотентность).
        2. При конфликте (duplicate key) — пропуск обработки.
        3. Возвращает email_log_id для передачи в Celery или None при дубликате.
        """
        logger.info("Processing incoming email event: event_uuid=%s", payload.event_uuid)

        existing = await self._repository.find_by_event_uuid(event_uuid=payload.event_uuid)
        if existing is not None:
            logger.warning(
                "Duplicate event_uuid=%s, existing id=%s status=%s — skipping",
                payload.event_uuid,
                existing["id"],
                existing["status"],
            )
            return None

        try:
            record = await self._repository.create(
                event_uuid=payload.event_uuid,
                to=payload.to,
                subject=payload.subject,
                body=payload.body,
                cc=payload.cc,
                bcc=payload.bcc,
                reply_to=payload.reply_to,
                from_name=payload.from_name,
                from_email=payload.from_email,
            )
        except Exception:
            logger.exception("Failed to create email_log for event_uuid=%s", payload.event_uuid)
            return None

        email_log_id = record["id"]
        logger.info("Created email_log id=%s, dispatching to Celery", email_log_id)
        return email_log_id

    async def complete_sending(
        self,
        *,
        email_log_id: UUID,
        repository: EmailLogRepositoryProtocol,
    ) -> dict:
        """
        Отправка email и обновление статуса.

        Вызывается из Celery task.
        Репозиторий передаётся извне (DI) с уже открытой сессией.
        Вся логика выполняется в рамках одной транзакции (сессии).
        """
        logger.info("complete_sending: email_log_id=%s", email_log_id)

        # Поиск записи
        record = await repository.find_by_id(email_log_id=email_log_id)
        if record is None:
            logger.error("Email log id=%s not found", email_log_id)
            return {"status": "error", "message": "not found"}

        # Увеличиваем счётчик попыток
        await repository.increment_attempts(email_log_id=email_log_id)

        # Отправляем email
        try:
            await self._email_sender.send(
                to=record["to"],
                subject=record["subject"],
                body=record["body"],
                cc=record["cc"],
                bcc=record["bcc"],
                reply_to=record["reply_to"],
                from_name=record["from_name"],
                from_email=record["from_email"],
            )
        except Exception as exc:
            logger.exception("SMTP send failed for email_log id=%s", email_log_id)
            await repository.update_status(
                email_log_id=email_log_id,
                status="failed",
                error_message=str(exc),
            )
            raise

        # Успех
        await repository.update_status(
            email_log_id=email_log_id,
            status="sent",
        )

        logger.info("Email sent successfully: email_log_id=%s", email_log_id)
        return {"status": "sent", "email_log_id": str(email_log_id)}
