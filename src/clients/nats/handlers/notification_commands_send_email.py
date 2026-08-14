import logging

from core.schemas.messaging import NotificationCommandSendEmailData
from core.services import NotificationCommandSendEmailService

logger = logging.getLogger(__name__)


class NotificationCommandsSendEmailHandler:
    def __init__(
        self,
        *,
        service: NotificationCommandSendEmailService,
    ) -> None:
        self._service = service

    async def handle(
        self,
        *,
        payload: bytes,
        headers: dict[str, str],
    ) -> None:
        event_data = NotificationCommandSendEmailData.model_validate_json(
            payload,
        )

        await self._service.process(
            payload=event_data,
        )
