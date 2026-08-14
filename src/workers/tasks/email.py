import asyncio
import logging
from uuid import UUID

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="email.send",
    autoretry_for=(Exception,),
    max_retries=3,
    retry_backoff=True,
)
def send_email_task(self, email_log_id: str) -> dict:
    """
    Celery task для отправки email.

    Создаёт сессию и репозиторий, передаёт в EmailProcessingService через DI.
    Вся логика выполняется в рамках одной транзакции.
    """
    logger.info("Celery task send_email_task: email_log_id=%s", email_log_id)

    try:
        result = asyncio.run(_send_email(email_log_id))
        logger.info("send_email_task completed: %s", result)
        return result
    except Exception:
        logger.exception("send_email_task failed for email_log_id=%s", email_log_id)
        raise


async def _send_email(email_log_id: str) -> dict:
    """Async helper для отправки email с DI и единой транзакцией."""
    from core.services.email_processing import EmailProcessingService
    from infrastructure.email_sender import SMTPEmailSender
    from repositories.email_log import SQLAlchemyEmailLogRepository
    from utils.database import SessionFactory

    async with SessionFactory() as session:
        try:
            repository = SQLAlchemyEmailLogRepository(session)
            email_sender = SMTPEmailSender()

            service = EmailProcessingService(
                repository=repository,
                email_sender=email_sender,
            )

            result = await service.complete_sending(
                email_log_id=UUID(email_log_id),
                repository=repository,
            )

            await session.commit()
            return result

        except Exception:
            await session.rollback()
            raise
