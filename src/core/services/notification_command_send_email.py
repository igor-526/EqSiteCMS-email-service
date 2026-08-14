import logging

from core.schemas.messaging import NotificationCommandSendEmailData

logger = logging.getLogger(__name__)


class NotificationCommandSendEmailService:
    async def process(
        self,
        *,
        payload: NotificationCommandSendEmailData,
    ) -> None:
        print(payload)
