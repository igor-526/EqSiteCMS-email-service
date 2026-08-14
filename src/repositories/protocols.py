from datetime import datetime
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

    async def log_action(
        self,
        *,
        action: str,
        status: str,
        details: dict | None = None,
    ) -> dict:
        """Создать запись в email_logs для логирования действий."""
        ...


class UserEmailRepositoryProtocol(Protocol):
    async def create(self, *, user_id: UUID, email: str) -> dict:
        """Создать запись о email пользователя. approved=false, deleted_at=None."""
        ...

    async def get_by_id(self, *, record_id: UUID) -> dict | None:
        """Получить запись по id записи (record id)."""
        ...

    async def get_by_user_id(self, *, user_id: UUID) -> dict | None:
        """Получить email пользователя по user_id (только не удалённые)."""
        ...

    async def get_by_user_ids(self, *, user_ids: list[UUID], approved: bool | None = None) -> list[dict]:
        """Получить emails по списку user_ids (только не удалённые)."""
        ...

    async def update_email(self, *, user_id: UUID, new_email: str) -> dict:
        """Обновить email. Если email совпадает — вернуть текущую запись."""
        ...

    async def soft_delete(self, *, user_id: UUID) -> bool:
        """Мягкое удаление. Идемпотентно: возвращает True всегда."""
        ...

    async def approve(self, *, user_id: UUID) -> None:
        """Подтвердить email пользователя."""
        ...


class EmailConfirmationRepositoryProtocol(Protocol):
    async def create(self, *, user_email_id: UUID, code: str, expires_at: datetime) -> dict:
        """Создать запись подтверждения."""
        ...

    async def get_by_code(self, *, code: str) -> dict | None:
        """Найти подтверждение по коду."""
        ...

    async def mark_used(self, *, confirmation_id: UUID) -> None:
        """Отметить подтверждение как использованное."""
        ...

    async def invalidate_previous(self, *, user_email_id: UUID) -> None:
        """Инвалидировать все предыдущие неиспользованные подтверждения."""
        ...
