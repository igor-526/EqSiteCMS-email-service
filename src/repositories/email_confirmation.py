import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.email_confirmation import email_confirmations

logger = logging.getLogger(__name__)


class SQLAlchemyEmailConfirmationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, user_email_id: UUID, code: str, expires_at: datetime) -> dict:
        """Создать запись подтверждения."""
        new_id = uuid4()
        now = datetime.now(UTC)
        stmt = (
            email_confirmations.insert()
            .values(
                id=new_id,
                user_email_id=user_email_id,
                code=code,
                expires_at=expires_at,
                created_at=now,
                used_at=None,
            )
            .returning(email_confirmations)
        )
        result = await self._session.execute(stmt)
        row = result.mappings().one()
        logger.info("Created email_confirmation id=%s user_email_id=%s", new_id, user_email_id)
        return dict(row)

    async def get_by_code(self, *, code: str) -> dict | None:
        """Найти подтверждение по коду."""
        stmt = select(email_confirmations).where(email_confirmations.c.code == code)
        result = await self._session.execute(stmt)
        row = result.mappings().one_or_none()
        return dict(row) if row else None

    async def mark_used(self, *, confirmation_id: UUID) -> None:
        """Отметить подтверждение как использованное."""
        now = datetime.now(UTC)
        stmt = update(email_confirmations).where(email_confirmations.c.id == confirmation_id).values(used_at=now)
        result = await self._session.execute(stmt)
        if result.rowcount > 0:  # type: ignore[attr-defined]
            logger.info("Marked email_confirmation id=%s as used", confirmation_id)
        else:
            logger.warning("No email_confirmation found to mark used id=%s", confirmation_id)

    async def invalidate_previous(self, *, user_email_id: UUID) -> None:
        """Инвалидировать все предыдущие неиспользованные подтверждения."""
        now = datetime.now(UTC)
        stmt = (
            update(email_confirmations)
            .where(
                email_confirmations.c.user_email_id == user_email_id,
                email_confirmations.c.used_at.is_(None),
            )
            .values(used_at=now)
        )
        result = await self._session.execute(stmt)
        logger.info(
            "Invalidated %d previous confirmations for user_email_id=%s",
            result.rowcount,  # type: ignore[attr-defined]
            user_email_id,
        )
