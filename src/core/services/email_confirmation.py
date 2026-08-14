import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from core.exceptions import ConflictError, GoneError, NotFoundError
from repositories.protocols import (
    EmailConfirmationRepositoryProtocol,
    EmailLogRepositoryProtocol,
    UserEmailRepositoryProtocol,
)

logger = logging.getLogger(__name__)


class EmailConfirmationService:
    def __init__(
        self,
        *,
        confirmation_repo: EmailConfirmationRepositoryProtocol,
        user_email_repo: UserEmailRepositoryProtocol,
        email_log_repo: EmailLogRepositoryProtocol,
        ttl_hours: int,
        frontend_url: str,
    ) -> None:
        self._confirmation_repo = confirmation_repo
        self._user_email_repo = user_email_repo
        self._email_log_repo = email_log_repo
        self._ttl_hours = ttl_hours
        self._frontend_url = frontend_url

    async def send_confirmation(self, user_id: UUID) -> str:
        """Отправить ссылку для подтверждения email."""
        logger.info("Sending confirmation for user_id=%s", user_id)

        user_email = await self._user_email_repo.get_by_user_id(user_id=user_id)
        if user_email is None:
            logger.warning("User email not found for user_id=%s", user_id)
            raise NotFoundError(f"User email not found for user_id={user_id}")

        record_id = user_email["id"]

        await self._confirmation_repo.invalidate_previous(user_email_id=record_id)

        code = uuid4().hex + secrets.token_hex(4)
        expires_at = datetime.now(UTC) + timedelta(hours=self._ttl_hours)

        await self._confirmation_repo.create(
            user_email_id=record_id,
            code=code,
            expires_at=expires_at,
        )

        confirmation_url = f"{self._frontend_url}/callback/email?code={code}"
        logger.info("Created confirmation for user_id=%s url=%s", user_id, confirmation_url)
        return confirmation_url

    async def confirm(self, code: str) -> dict:
        """Подтвердить email по коду."""
        logger.info("Confirming email with code=%s", code[:8] + "...")

        confirmation = await self._confirmation_repo.get_by_code(code=code)

        if confirmation is None:
            logger.warning("Confirmation code not found: %s", code[:8] + "...")
            await self._email_log_repo.log_action(
                action="email_confirmation",
                status="not_found",
                details={"code": code},
            )
            raise NotFoundError("Confirmation code not found")

        confirmation_id = confirmation["id"]
        user_email_record_id = confirmation["user_email_id"]
        used_at = confirmation["used_at"]
        expires_at = confirmation["expires_at"]

        if used_at is not None:
            logger.warning("Confirmation code already used: id=%s", confirmation_id)
            await self._email_log_repo.log_action(
                action="email_confirmation",
                status="used",
                details={"confirmation_id": str(confirmation_id), "code": code},
            )
            raise ConflictError("Confirmation link already used")

        if expires_at <= datetime.now(UTC):
            logger.warning("Confirmation code expired: id=%s", confirmation_id)
            await self._email_log_repo.log_action(
                action="email_confirmation",
                status="expired",
                details={"confirmation_id": str(confirmation_id), "code": code},
            )
            raise GoneError("Confirmation link expired")

        # Получаем user_id из записи user_email
        user_email_record = await self._user_email_repo.get_by_id(record_id=user_email_record_id)
        if user_email_record is None:
            logger.error("User email record not found for id=%s", user_email_record_id)
            await self._email_log_repo.log_action(
                action="email_confirmation",
                status="error",
                details={"confirmation_id": str(confirmation_id), "reason": "user_email_not_found"},
            )
            raise NotFoundError("User email record not found")

        user_id = user_email_record["user_id"]

        # Подтверждаем email
        await self._user_email_repo.approve(user_id=user_id)

        # Пометить код использованным
        await self._confirmation_repo.mark_used(confirmation_id=confirmation_id)

        # Логировать успех
        await self._email_log_repo.log_action(
            action="email_confirmation",
            status="success",
            details={
                "confirmation_id": str(confirmation_id),
                "user_email_id": str(user_email_record_id),
                "user_id": str(user_id),
            },
        )

        logger.info("Email confirmed successfully: user_id=%s", user_id)
        return {"status": "confirmed", "user_email_id": str(user_email_record_id)}
