from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.email_confirmation import EmailConfirmationService
from core.services.user_email import UserEmailService
from repositories.email_confirmation import SQLAlchemyEmailConfirmationRepository
from repositories.email_log import SQLAlchemyEmailLogRepository
from repositories.user_email import SQLAlchemyUserEmailRepository
from settings import settings
from utils.database import get_session


async def get_user_email_service(
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> UserEmailService:
    user_email_repo = SQLAlchemyUserEmailRepository(session)
    email_log_repo = SQLAlchemyEmailLogRepository(session)
    return UserEmailService(
        user_email_repo=user_email_repo,
        email_log_repo=email_log_repo,
    )


async def get_email_confirmation_service(
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EmailConfirmationService:
    confirmation_repo = SQLAlchemyEmailConfirmationRepository(session)
    user_email_repo = SQLAlchemyUserEmailRepository(session)
    email_log_repo = SQLAlchemyEmailLogRepository(session)
    return EmailConfirmationService(
        confirmation_repo=confirmation_repo,
        user_email_repo=user_email_repo,
        email_log_repo=email_log_repo,
        ttl_hours=settings.email_confirmation_ttl_hours,
        frontend_url=settings.frontend_url,
    )
