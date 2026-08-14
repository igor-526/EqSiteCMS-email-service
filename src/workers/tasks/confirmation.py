import asyncio
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="email.send_confirmation",
    autoretry_for=(Exception,),
    max_retries=3,
    retry_backoff=True,
)
def send_confirmation_email_task(self, user_id: str) -> dict:
    """Celery task для отправки письма подтверждения email."""
    logger.info("Celery task send_confirmation_email_task: user_id=%s", user_id)
    try:
        result = asyncio.run(_send_confirmation_email(user_id))
        logger.info("send_confirmation_email_task completed: %s", result)
        return result
    except Exception:
        logger.exception("send_confirmation_email_task failed for user_id=%s", user_id)
        raise


async def _send_confirmation_email(user_id: str) -> dict:
    """Async helper для отправки письма подтверждения."""
    from infrastructure.email_sender import SMTPEmailSender
    from repositories.email_confirmation import SQLAlchemyEmailConfirmationRepository
    from repositories.email_log import SQLAlchemyEmailLogRepository
    from repositories.user_email import SQLAlchemyUserEmailRepository
    from settings import settings
    from utils.database import SessionFactory

    async with SessionFactory() as session:
        try:
            user_email_repo = SQLAlchemyUserEmailRepository(session)
            confirmation_repo = SQLAlchemyEmailConfirmationRepository(session)
            email_log_repo = SQLAlchemyEmailLogRepository(session)
            email_sender = SMTPEmailSender()

            # 1. Найти email пользователя
            user_email = await user_email_repo.get_by_user_id(user_id=UUID(user_id))
            if user_email is None:
                logger.warning("User email not found for user_id=%s", user_id)
                await email_log_repo.log_action(
                    action="send_confirmation",
                    status="error",
                    details={"user_id": user_id, "reason": "email_not_found"},
                )
                await session.commit()
                return {"status": "error", "message": "email not found"}

            email = user_email["email"]
            record_id = user_email["id"]

            # 2. Инвалидировать предыдущие коды
            await confirmation_repo.invalidate_previous(user_email_id=record_id)

            # 3. Сгенерировать новый код (40 символов)
            code = uuid4().hex + secrets.token_hex(4)

            # 4. Вычислить expires_at
            ttl_hours = settings.email_confirmation_ttl_hours
            expires_at = datetime.now(UTC) + timedelta(hours=ttl_hours)

            # 5. Создать запись подтверждения
            await confirmation_repo.create(
                user_email_id=record_id,
                code=code,
                expires_at=expires_at,
            )

            # 6. Сформировать ссылку
            confirmation_url = f"{settings.frontend_url}/callback/email?code={code}"

            # 7. Сформировать HTML body
            html_body = (
                "<h2>Подтверждение email</h2>"
                "<p>Для подтверждения вашего email перейдите по ссылке:</p>"
                f'<p><a href="{confirmation_url}">{confirmation_url}</a></p>'
                f"<p>Ссылка действительна в течение {ttl_hours} часов.</p>"
                "<p>Если вы не запрашивали подтверждение, просто игнорируйте это письмо.</p>"
            )

            # 8. Отправить email
            await email_sender.send(
                to=[email],
                subject="Подтверждение email",
                body=html_body,
            )

            # 9. Логировать успех
            await email_log_repo.log_action(
                action="send_confirmation",
                status="sent",
                details={"user_id": user_id, "email": email, "confirmation_url": confirmation_url},
            )

            await session.commit()
            logger.info("Confirmation email sent to %s for user_id=%s", email, user_id)
            return {"status": "sent", "email": email}

        except Exception:
            await session.rollback()
            raise
