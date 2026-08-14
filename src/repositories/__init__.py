from .email_log import SQLAlchemyEmailLogRepository
from .protocols import EmailLogRepositoryProtocol

__all__ = [
    "EmailLogRepositoryProtocol",
    "SQLAlchemyEmailLogRepository",
]
