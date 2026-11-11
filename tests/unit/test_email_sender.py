import logging
import ssl
from unittest.mock import AsyncMock

import pytest
from aiosmtplib.errors import SMTPException, SMTPNotSupported

from infrastructure import email_sender
from settings import SMTPSettings


@pytest.fixture
def smtp_client(monkeypatch):
    client = AsyncMock()
    monkeypatch.setattr(email_sender.aiosmtplib, "send", client)
    return client


def configure(monkeypatch, **values):
    config = SMTPSettings(
        SMTP_HOST="smtp.synthetic.invalid",
        SMTP_USER="SYNTHETIC_KEY_MARKER",
        SMTP_PASSWORD="SYNTHETIC_PASSWORD_MARKER",
        EMAIL_FROM="default@example.invalid",
        _env_file=None,
        **values,
    )
    monkeypatch.setattr(email_sender, "smtp_settings", config)
    return config


@pytest.mark.parametrize("port", (1127, 1126, 465, 587, 2525))
@pytest.mark.parametrize("mode", ("tls", "starttls", "none"))
async def test_explicit_transport_flags(port, mode, monkeypatch, smtp_client):
    config = configure(monkeypatch, SMTP_PORT=port, SMTP_TLS_MODE=mode)
    await email_sender.SMTPEmailSender().send(
        to=["to@example.invalid"],
        subject="SYNTHETIC_SUBJECT_MARKER",
        body="<p>SYNTHETIC_BODY_MARKER</p>",
        cc=["cc@example.invalid"],
        bcc=["bcc@example.invalid"],
        reply_to="reply@example.invalid",
        from_name="Synthetic sender",
        from_email="override@example.invalid",
    )
    smtp_client.assert_awaited_once()
    kwargs = smtp_client.call_args.kwargs
    assert kwargs["use_tls"] is (mode == "tls")
    assert kwargs["start_tls"] is (mode == "starttls")
    assert kwargs["validate_certs"] is True
    assert kwargs["hostname"] == config.smtp_host
    assert kwargs["port"] == port
    assert kwargs["username"] == config.smtp_user
    assert kwargs["password"] == config.smtp_password
    assert kwargs["recipients"] == ["to@example.invalid", "cc@example.invalid", "bcc@example.invalid"]
    msg = smtp_client.call_args.args[0]
    assert msg["From"] == "Synthetic sender <override@example.invalid>"
    assert msg["To"] == "to@example.invalid"
    assert msg["Cc"] == "cc@example.invalid"
    assert msg["Bcc"] is None
    assert msg["Reply-To"] == "reply@example.invalid"
    assert msg["Subject"] == "SYNTHETIC_SUBJECT_MARKER"
    assert msg.get_content_type() == "multipart/alternative"
    part = next(msg.walk())  # Multipart container is unchanged.
    assert part.is_multipart()
    html = msg.get_payload()[0]
    assert html.get_content_type() == "text/html"
    assert html.get_content_charset() == "utf-8"
    assert html.get_payload(decode=True).decode("utf-8") == "<p>SYNTHETIC_BODY_MARKER</p>"


async def test_default_envelope_and_empty_credentials(monkeypatch, smtp_client):
    monkeypatch.setattr(email_sender, "smtp_settings", SMTPSettings(_env_file=None, EMAIL_FROM="from@example.invalid"))
    await email_sender.SMTPEmailSender().send(to=["to@example.invalid"], subject="synthetic", body="synthetic")
    kwargs = smtp_client.call_args.kwargs
    assert kwargs["username"] is None
    assert kwargs["password"] is None
    assert kwargs["recipients"] == ["to@example.invalid"]
    msg = smtp_client.call_args.args[0]
    assert msg["From"] == "from@example.invalid <from@example.invalid>"
    assert msg["Cc"] is None
    assert msg["Reply-To"] is None


@pytest.mark.parametrize("mode", ("tls", "starttls"))
@pytest.mark.parametrize(
    "error_type",
    (ssl.SSLCertVerificationError, ssl.SSLError, SMTPNotSupported, TimeoutError, SMTPException),
)
async def test_transport_errors_do_not_downgrade(mode, error_type, monkeypatch, smtp_client):
    configure(monkeypatch, SMTP_PORT=1127, SMTP_TLS_MODE=mode)
    error = error_type("synthetic transport failure")
    smtp_client.side_effect = error
    sender = email_sender.SMTPEmailSender()
    for attempt in (1, 2):
        with pytest.raises(error_type) as caught:
            await sender.send(to=["to@example.invalid"], subject="synthetic", body="synthetic")
        assert caught.value is error
        assert smtp_client.await_count == attempt
        kwargs = smtp_client.call_args.kwargs
        assert kwargs["use_tls"] is (mode == "tls")
        assert kwargs["start_tls"] is (mode == "starttls")
        assert kwargs["validate_certs"] is True


@pytest.mark.parametrize("failure", (False, True))
async def test_safe_transport_logging(failure, monkeypatch, smtp_client, caplog):
    configure(monkeypatch, SMTP_TLS_MODE="tls", SMTP_PORT=1127)
    if failure:
        smtp_client.side_effect = TimeoutError("SYNTHETIC_EXCEPTION_MARKER")
    with caplog.at_level(logging.INFO, logger=email_sender.__name__):
        try:
            await email_sender.SMTPEmailSender().send(
                to=["to@example.invalid"], subject="SYNTHETIC_SUBJECT_MARKER", body="SYNTHETIC_BODY_MARKER"
            )
        except TimeoutError:
            assert failure
    own_logs = "\n".join(record.getMessage() for record in caplog.records if record.name == email_sender.__name__)
    assert "Sending email via SMTP" in own_logs
    assert "SYNTHETIC_" not in own_logs
    assert ("Email sent successfully" in own_logs) is not failure


async def test_selectel_1127_legacy_regression(monkeypatch, smtp_client):
    configure(monkeypatch, SMTP_PORT=1127, SMTP_USE_TLS=True)
    await email_sender.SMTPEmailSender().send(to=["to@example.invalid"], subject="synthetic", body="synthetic")
    smtp_client.assert_awaited_once()
    kwargs = smtp_client.call_args.kwargs
    assert kwargs["use_tls"] is True
    assert kwargs["start_tls"] is False
    assert kwargs["validate_certs"] is True
