"""Тесты модели email_confirmations."""

from models.email_confirmation import email_confirmations


def test_email_confirmations_table_exists():
    assert email_confirmations.name == "email_confirmations"


def test_email_confirmations_has_code_column():
    assert "code" in email_confirmations.c


def test_email_confirmations_has_expires_at_column():
    assert "expires_at" in email_confirmations.c


def test_email_confirmations_has_used_at_column():
    assert "used_at" in email_confirmations.c
