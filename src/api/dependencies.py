from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.email_confirmation import EmailConfirmationService
from core.services.user_email import UserEmailService
from repositories.email_confirmation import SQLAlchemyEmailConfirmationRepository
from repositories.email_log import SQLAlchemyEmailLogRepository
from repositories.user_email import SQLAlchemyUserEmailRepository
from settings import main_backend_settings, settings
from utils.database import get_session

security = HTTPBearer()


async def verify_service_key(
    credentials: HTTPAuthorizationCredentials = Security(security),  # noqa: B008
) -> str:
    if credentials.credentials != main_backend_settings.main_backend_service_key:
        raise HTTPException(status_code=401, detail="Invalid service key")
    return credentials.credentials


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
