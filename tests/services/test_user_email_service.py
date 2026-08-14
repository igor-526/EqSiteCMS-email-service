"""Тесты UserEmailService."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from core.exceptions import AlreadyExistsError
from core.services.user_email import UserEmailService


@pytest.fixture
def mock_user_email_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_email_log_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def service(mock_user_email_repo, mock_email_log_repo):
    return UserEmailService(
        user_email_repo=mock_user_email_repo,
        email_log_repo=mock_email_log_repo,
    )


async def test_create_email(service, mock_user_email_repo):
    user_id = uuid4()
    expected = {"user_id": user_id, "email": "test@example.com", "approved": False}
    mock_user_email_repo.create.return_value = expected

    result = await service.create_email(user_id, "test@example.com")

    assert result == expected
    mock_user_email_repo.create.assert_called_once_with(user_id=user_id, email="test@example.com")


async def test_create_email_already_exists(service, mock_user_email_repo):
    user_id = uuid4()
    mock_user_email_repo.create.side_effect = AlreadyExistsError("duplicate")

    with pytest.raises(AlreadyExistsError):
        await service.create_email(user_id, "test@example.com")


async def test_get_user_email(service, mock_user_email_repo):
    user_id = uuid4()
    expected = {"user_id": user_id, "email": "test@example.com", "approved": True}
    mock_user_email_repo.get_by_user_id.return_value = expected

    result = await service.get_user_email(user_id)

    assert result == expected


async def test_get_user_email_not_found(service, mock_user_email_repo):
    mock_user_email_repo.get_by_user_id.return_value = None

    result = await service.get_user_email(uuid4())

    assert result is None


async def test_change_email(service, mock_user_email_repo):
    user_id = uuid4()
    expected = {"user_id": user_id, "email": "new@example.com", "approved": False}
    mock_user_email_repo.update_email.return_value = expected

    result = await service.change_email(user_id, "new@example.com")

    assert result == expected


async def test_delete_email(service, mock_user_email_repo):
    mock_user_email_repo.soft_delete.return_value = True

    result = await service.delete_email(uuid4())

    assert result is True


async def test_approve_email(service, mock_user_email_repo):
    await service.approve_email(uuid4())
    mock_user_email_repo.approve.assert_called_once()
