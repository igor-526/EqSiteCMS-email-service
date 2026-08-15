import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import AlreadyExistsError, NotFoundError
from models.user_email import user_emails

logger = logging.getLogger(__name__)


class SQLAlchemyUserEmailRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, user_id: UUID, email: str) -> dict:
        """Создать запись о email пользователя."""
        now = datetime.now(UTC)
        stmt = (
            user_emails.insert()
            .values(
                user_id=user_id,
                email=email,
                approved=False,
                deleted_at=None,
                created_at=now,
                updated_at=now,
            )
            .returning(user_emails)
        )
        try:
            result = await self._session.execute(stmt)
            row = result.mappings().one()
            logger.info("Created user_email id=%s user_id=%s email=%s", row["id"], user_id, email)
            return dict(row)
        except IntegrityError as e:
            await self._session.rollback()
            logger.warning(
                "IntegrityError creating user_email user_id=%s email=%s: %s",
                user_id,
                email,
                str(e),
            )
            raise AlreadyExistsError(f"User email already exists for user_id={user_id} or email={email}") from e

    async def get_by_id(self, *, record_id: UUID) -> dict | None:
        """Получить запись по id записи (record id)."""
        stmt = select(user_emails).where(user_emails.c.id == record_id)
        result = await self._session.execute(stmt)
        row = result.mappings().one_or_none()
        return dict(row) if row else None

    async def get_by_user_id(self, *, user_id: UUID) -> dict | None:
        """Получить email пользователя по user_id (только не удалённые)."""
        stmt = select(user_emails).where(
            user_emails.c.user_id == user_id,
            user_emails.c.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        row = result.mappings().one_or_none()
        return dict(row) if row else None

    async def get_by_user_ids(self, *, user_ids: list[UUID], approved: bool | None = None) -> list[dict]:
        """Получить emails по списку user_ids (только не удалённые)."""
        stmt = select(user_emails).where(
            user_emails.c.user_id.in_(user_ids),
            user_emails.c.deleted_at.is_(None),
        )
        if approved is not None:
            stmt = stmt.where(user_emails.c.approved == approved)
        result = await self._session.execute(stmt)
        rows = result.mappings().all()
        return [dict(row) for row in rows]

    async def update_email(self, *, user_id: UUID, new_email: str) -> dict:
        """Обновить email. Если email совпадает — вернуть текущую запись."""
        current = await self.get_by_user_id(user_id=user_id)
        if current is None:
            raise NotFoundError(f"User email not found for user_id={user_id}")

        if current["email"] == new_email:
            logger.info("Email unchanged for user_id=%s, returning current record", user_id)
            return current

        now = datetime.now(UTC)
        stmt = (
            update(user_emails)
            .where(
                user_emails.c.user_id == user_id,
                user_emails.c.deleted_at.is_(None),
            )
            .values(
                email=new_email,
                approved=False,
                updated_at=now,
            )
            .returning(user_emails)
        )
        result = await self._session.execute(stmt)
        row = result.mappings().one()
        logger.info("Updated email for user_id=%s to %s", user_id, new_email)
        return dict(row)

    async def soft_delete(self, *, user_id: UUID) -> bool:
        """Мягкое удаление. Идемпотентно: возвращает True всегда."""
        now = datetime.now(UTC)
        stmt = (
            update(user_emails)
            .where(
                user_emails.c.user_id == user_id,
                user_emails.c.deleted_at.is_(None),
            )
            .values(deleted_at=now)
        )
        result = await self._session.execute(stmt)
        if result.rowcount > 0:  # type: ignore[attr-defined]
            logger.info("Soft deleted user_email user_id=%s", user_id)
        else:
            logger.info("User email already deleted or not found user_id=%s", user_id)
        return True

    async def approve(self, *, user_id: UUID) -> None:
        """Подтвердить email пользователя по user_id."""
        now = datetime.now(UTC)
        stmt = (
            update(user_emails)
            .where(
                user_emails.c.user_id == user_id,
                user_emails.c.deleted_at.is_(None),
            )
            .values(
                approved=True,
                updated_at=now,
            )
        )
        result = await self._session.execute(stmt)
        if result.rowcount > 0:  # type: ignore[attr-defined]
            logger.info("Approved user_email user_id=%s", user_id)
        else:
            logger.warning("No user_email found to approve user_id=%s", user_id)
