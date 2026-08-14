from typing import Protocol


class EmailPublisher(Protocol):
    async def publish(
        self,
        *,
        recipient: str,
        subject: str,
        body: str,
    ) -> None: ...
