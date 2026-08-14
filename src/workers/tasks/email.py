from celery import shared_task


@shared_task(
    bind=True,
    name="email.send",
    autoretry_for=(Exception,),
    max_retries=3,
    retry_backoff=True,
)
def send_email_task(self, recipient: str, subject: str, body: str) -> dict:
    """Отправка email через очередь."""
    # TODO: интеграция с реальным email-провайдером (SMTP/API)
    # service = NotificationCommandSendEmailService()
    # result = service.process_sync(recipient=recipient, subject=subject, body=body)
    return {"status": "sent", "recipient": recipient}
