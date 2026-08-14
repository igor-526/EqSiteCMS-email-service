from typing import Protocol


class NotificationCommandSendEmailHandlerProtocol(Protocol):
    async def handle(
        self,
        *,
        payload: bytes,
        headers: dict[str, str],
    ) -> None: ...
