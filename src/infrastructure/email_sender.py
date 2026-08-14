import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from settings import smtp_settings

logger = logging.getLogger(__name__)


class SMTPEmailSender:
    """Отправка email через SMTP (aiosmtplib)."""

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
        from_addr = from_email or smtp_settings.email_from
        sender_display = from_name or from_addr

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{sender_display} <{from_addr}>"
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject

        if cc:
            msg["Cc"] = ", ".join(cc)
        if reply_to:
            msg["Reply-To"] = reply_to

        msg.attach(MIMEText(body, "html", "utf-8"))

        all_recipients = list(to)
        if cc:
            all_recipients.extend(cc)
        if bcc:
            all_recipients.extend(bcc)

        logger.info(
            "Sending email via SMTP: from=%s to=%s subject=%s",
            from_addr,
            all_recipients,
            subject,
        )

        # Port 465 = implicit TLS (SSL), Port 587 = STARTTLS
        use_tls = smtp_settings.smtp_port == 465
        starttls = smtp_settings.smtp_port == 587

        await aiosmtplib.send(
            msg,
            hostname=smtp_settings.smtp_host,
            port=smtp_settings.smtp_port,
            username=smtp_settings.smtp_user or None,
            password=smtp_settings.smtp_password or None,
            use_tls=use_tls,
            start_tls=starttls,
            recipients=all_recipients,
        )

        logger.info("Email sent successfully to %s", all_recipients)
