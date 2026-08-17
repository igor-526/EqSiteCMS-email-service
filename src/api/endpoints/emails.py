from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.dependencies import get_email_confirmation_service, get_user_email_service
from api.schemas.email import (
    ConfirmationResponse,
    EmailConfirmRequest,
    EmailCreateRequest,
    EmailResponse,
    EmailSendConfirmationRequest,
    EmailUpdateRequest,
)
from core.exceptions import NotFoundError
from core.services.email_confirmation import EmailConfirmationService
from core.services.user_email import UserEmailService

router = APIRouter(prefix="/emails")


@router.get("", response_model=list[EmailResponse])
async def get_emails(
    user_ids: str = Query(..., description="Comma-separated list of UUIDs"),
    approved: bool | None = Query(None, description="Filter by approved status"),
    service: UserEmailService = Depends(get_user_email_service),  # noqa: B008
) -> list[dict]:
    """Получить email'ы по списку user_ids (Public Read)."""
    parsed_ids = [UUID(uid.strip()) for uid in user_ids.split(",")]
    return await service.get_user_emails(user_ids=parsed_ids, approved=approved)


@router.post("", response_model=EmailResponse, status_code=201)
async def create_email(
    body: EmailCreateRequest,
    service: UserEmailService = Depends(get_user_email_service),  # noqa: B008
) -> dict:
    """Создать email пользователя (Protected Write)."""
    return await service.create_email(user_id=body.user_id, email=body.email)


@router.patch("", response_model=EmailResponse)
async def update_email(
    body: EmailUpdateRequest,
    service: UserEmailService = Depends(get_user_email_service),  # noqa: B008
) -> dict:
    """Обновить email пользователя (Protected Write)."""
    return await service.change_email(user_id=body.user_id, new_email=body.email)


@router.delete("/{user_id}", status_code=204)
async def delete_email(
    user_id: UUID,
    service: UserEmailService = Depends(get_user_email_service),  # noqa: B008
) -> None:
    """Мягкое удаление email пользователя (Protected Write)."""
    await service.delete_email(user_id=user_id)


@router.patch("/confirm", response_model=ConfirmationResponse)
async def confirm_email(
    body: EmailConfirmRequest,
    service: EmailConfirmationService = Depends(get_email_confirmation_service),  # noqa: B008
) -> dict:
    """Подтвердить email по коду (Protected Write)."""
    return await service.confirm(code=body.code)


@router.post("/send-confirmation", status_code=202)
async def send_confirmation(
    body: EmailSendConfirmationRequest,
    service: UserEmailService = Depends(get_user_email_service),  # noqa: B008
) -> JSONResponse:
    """Отправить ссылку для подтверждения email (Protected Write).

    Проверяет существование email, затем диспатчит Celery task для отправки письма.
    """
    # Проверяем что email существует
    user_email = await service.get_user_email(user_id=body.user_id)
    if user_email is None:
        raise NotFoundError(f"User email not found for user_id={body.user_id}")

    # Диспатчим Celery task
    from workers.tasks.confirmation import send_confirmation_email_task

    cast(Any, send_confirmation_email_task).delay(str(body.user_id))

    return JSONResponse(
        status_code=202,
        content={"detail": "Confirmation email queued for sending"},
    )
