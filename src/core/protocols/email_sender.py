from typing import Protocol


class EmailSenderProtocol(Protocol):
    async def send(
        self,
        *,
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to: str | None = None,
        from_name: str | None = None,
        from_email: str | None = None,
    ) -> None:
        """Отправить email через SMTP."""
        ...
