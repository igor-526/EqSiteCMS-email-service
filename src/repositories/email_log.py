import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.email_log import email_logs

logger = logging.getLogger(__name__)


class SQLAlchemyEmailLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        event_uuid: UUID,
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to: str | None = None,
        from_name: str | None = None,
        from_email: str | None = None,
    ) -> dict | None:
        """Создать запись в email_logs с идемпотентностью по event_uuid."""
        now = datetime.now(UTC)
        new_id = uuid4()

        stmt = (
            pg_insert(email_logs)
            .values(
                id=new_id,
                event_uuid=event_uuid,
                to=to,
                subject=subject,
                body=body,
                cc=cc,
                bcc=bcc,
                reply_to=reply_to,
                from_name=from_name,
                from_email=from_email,
                status="pending",
                attempts=0,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["event_uuid"])
            .returning(email_logs)
        )
        result = await self._session.execute(stmt)
        row = result.mappings().one_or_none()

        if row is None:
            logger.info("Email log with event_uuid=%s already exists, skipping", event_uuid)
            return None

        logger.info("Created email_log id=%s event_uuid=%s", row["id"], event_uuid)
        return dict(row)

    async def update_status(
        self,
        *,
        email_log_id: UUID,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Обновить статус записи."""
        now = datetime.now(UTC)
        values: dict = {
            "status": status,
            "updated_at": now,
        }
        if error_message is not None:
            values["error_message"] = error_message
        if status == "sent":
            values["sent_at"] = now

        stmt = update(email_logs).where(email_logs.c.id == email_log_id).values(**values)
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("Updated email_log id=%s status=%s", email_log_id, status)

    async def find_by_event_uuid(self, *, event_uuid: UUID) -> dict | None:
        """Найти запись по event_uuid."""
        stmt = select(email_logs).where(email_logs.c.event_uuid == event_uuid)
        result = await self._session.execute(stmt)
        row = result.mappings().one_or_none()
        return dict(row) if row else None

    async def find_by_id(self, *, email_log_id: UUID) -> dict | None:
        """Найти запись по id."""
        stmt = select(email_logs).where(email_logs.c.id == email_log_id)
        result = await self._session.execute(stmt)
        row = result.mappings().one_or_none()
        return dict(row) if row else None

    async def increment_attempts(self, *, email_log_id: UUID) -> None:
        """Увеличить счётчик попыток."""
        now = datetime.now(UTC)
        stmt = (
            update(email_logs)
            .where(email_logs.c.id == email_log_id)
            .values(
                attempts=email_logs.c.attempts + 1,
                updated_at=now,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("Incremented attempts for email_log id=%s", email_log_id)

    async def log_action(
        self,
        *,
        action: str,
        status: str,
        details: dict | None = None,
    ) -> dict:
        """Создать запись в email_logs для логирования действий (не email-отправок)."""
        now = datetime.now(UTC)
        new_id = uuid4()

        stmt = (
            pg_insert(email_logs)
            .values(
                id=new_id,
                event_uuid=uuid4(),
                to=[],
                subject=action,
                body=json.dumps(details or {}),
                status=status,
                attempts=0,
                created_at=now,
                updated_at=now,
            )
            .returning(email_logs)
        )
        result = await self._session.execute(stmt)
        row = result.mappings().one()
        logger.info("Logged action=%s status=%s id=%s", action, status, row["id"])
        return dict(row)
