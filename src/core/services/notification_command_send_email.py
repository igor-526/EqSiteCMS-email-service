import logging

from core.schemas.messaging import NotificationCommandSendEmailData

logger = logging.getLogger(__name__)


class NotificationCommandSendEmailService:
    async def process(
        self,
        *,
        payload: NotificationCommandSendEmailData,
    ) -> None:
        logger.info("Processing notification command: event_uuid=%s", payload.event_uuid)
