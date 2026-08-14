import logging
from uuid import UUID

from repositories.protocols import EmailLogRepositoryProtocol, UserEmailRepositoryProtocol

logger = logging.getLogger(__name__)


class UserEmailService:
    def __init__(
        self,
        *,
        user_email_repo: UserEmailRepositoryProtocol,
        email_log_repo: EmailLogRepositoryProtocol,
    ) -> None:
        self._user_email_repo = user_email_repo
        self._email_log_repo = email_log_repo

    async def create_email(self, user_id: UUID, email: str) -> dict:
        """Создать запись о email пользователя."""
        logger.info("Creating email for user_id=%s email=%s", user_id, email)
        return await self._user_email_repo.create(user_id=user_id, email=email)

    async def get_user_email(self, user_id: UUID) -> dict | None:
        """Получить email пользователя по user_id."""
        logger.info("Getting email for user_id=%s", user_id)
        return await self._user_email_repo.get_by_user_id(user_id=user_id)

    async def get_user_emails(self, user_ids: list[UUID], approved: bool | None = None) -> list[dict]:
        """Получить emails по списку user_ids."""
        logger.info("Getting emails for user_ids=%s approved=%s", user_ids, approved)
        return await self._user_email_repo.get_by_user_ids(user_ids=user_ids, approved=approved)

    async def change_email(self, user_id: UUID, new_email: str) -> dict:
        """Обновить email пользователя."""
        logger.info("Changing email for user_id=%s to %s", user_id, new_email)
        return await self._user_email_repo.update_email(user_id=user_id, new_email=new_email)

    async def delete_email(self, user_id: UUID) -> bool:
        """Мягкое удаление email пользователя."""
        logger.info("Deleting email for user_id=%s", user_id)
        return await self._user_email_repo.soft_delete(user_id=user_id)

    async def approve_email(self, user_id: UUID) -> None:
        """Подтвердить email пользователя."""
        logger.info("Approving email for user_id=%s", user_id)
        await self._user_email_repo.approve(user_id=user_id)
