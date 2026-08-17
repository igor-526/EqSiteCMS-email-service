"""Тесты EmailConfirmationService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from core.exceptions import ClientError, ConflictError, GoneError, NotFoundError
from core.services.email_confirmation import EmailConfirmationService


@pytest.fixture
def mock_confirmation_repo():
    return AsyncMock()


@pytest.fixture
def mock_user_email_repo():
    return AsyncMock()


@pytest.fixture
def mock_email_log_repo():
    return AsyncMock()


@pytest.fixture
def service(mock_confirmation_repo, mock_user_email_repo, mock_email_log_repo):
    return EmailConfirmationService(
        confirmation_repo=mock_confirmation_repo,
        user_email_repo=mock_user_email_repo,
        email_log_repo=mock_email_log_repo,
        ttl_hours=24,
        frontend_url="http://localhost:3000",
    )


async def test_send_confirmation_success(service, mock_user_email_repo, mock_confirmation_repo):
    user_id = uuid4()
    mock_user_email_repo.get_by_user_id.return_value = {"id": uuid4(), "user_id": user_id, "email": "test@example.com"}

    result = await service.send_confirmation(user_id)

    assert "/callback/email?code=" in result
    mock_confirmation_repo.invalidate_previous.assert_called_once()
    mock_confirmation_repo.create.assert_called_once()


async def test_send_confirmation_email_not_found(service, mock_user_email_repo):
    mock_user_email_repo.get_by_user_id.return_value = None

    with pytest.raises(NotFoundError):
        await service.send_confirmation(uuid4())


async def test_confirm_success(service, mock_confirmation_repo, mock_user_email_repo, mock_email_log_repo):
    confirmation_id = uuid4()
    user_email_id = uuid4()
    mock_confirmation_repo.get_by_code.return_value = {
        "id": confirmation_id,
        "user_email_id": user_email_id,
        "used_at": None,
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }

    result = await service.confirm("valid_code_1234567890123456")

    assert result["status"] == "confirmed"
    mock_user_email_repo.approve.assert_called_once()
    mock_confirmation_repo.mark_used.assert_called_once()


async def test_confirm_code_not_found(service, mock_confirmation_repo, mock_email_log_repo):
    mock_confirmation_repo.get_by_code.return_value = None

    with pytest.raises(ClientError) as exc_info:
        await service.confirm("nonexistent_code_1234567890")

    assert exc_info.value.status_code == 400


async def test_confirm_code_expired(service, mock_confirmation_repo, mock_email_log_repo):
    mock_confirmation_repo.get_by_code.return_value = {
        "id": uuid4(),
        "user_email_id": uuid4(),
        "used_at": None,
        "expires_at": datetime.now(UTC) - timedelta(hours=1),
    }

    with pytest.raises(GoneError):
        await service.confirm("expired_code_12345678901234")


async def test_confirm_code_already_used(service, mock_confirmation_repo, mock_email_log_repo):
    mock_confirmation_repo.get_by_code.return_value = {
        "id": uuid4(),
        "user_email_id": uuid4(),
        "used_at": datetime.now(UTC),
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }

    with pytest.raises(ConflictError):
        await service.confirm("used_code_123456789012345")
