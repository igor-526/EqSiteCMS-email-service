from typing import Protocol
from uuid import UUID


class EmailLogRepositoryProtocol(Protocol):
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
    ) -> dict:
        """Создать запись в email_logs. Возвращает созданную запись."""
        ...

    async def update_status(
        self,
        *,
        email_log_id: UUID,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Обновить статус записи (sent/failed)."""
        ...

    async def find_by_event_uuid(self, *, event_uuid: UUID) -> dict | None:
        """Найти запись по event_uuid."""
        ...

    async def find_by_id(self, *, email_log_id: UUID) -> dict | None:
        """Найти запись по id."""
        ...

    async def increment_attempts(self, *, email_log_id: UUID) -> None:
        """Увеличить счётчик попыток."""
        ...
