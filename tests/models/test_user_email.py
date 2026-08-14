"""Тесты модели user_emails."""

from models.user_email import user_emails


def test_user_emails_table_exists():
    assert user_emails.name == "user_emails"


def test_user_emails_has_user_id_column():
    assert "user_id" in user_emails.c


def test_user_emails_has_email_column():
    assert "email" in user_emails.c


def test_user_emails_has_approved_column():
    assert "approved" in user_emails.c


def test_user_emails_has_deleted_at_column():
    assert "deleted_at" in user_emails.c
