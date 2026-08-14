"""Тесты API endpoints для email."""

from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from api.dependencies import get_user_email_service
from main import app


# Мокаем service key verification
async def mock_verify_service_key():
    return "test-key"


# Создаём мок сервиса
def make_mock_user_email_service():
    service = AsyncMock()
    return service


def make_mock_confirmation_service():
    service = AsyncMock()
    return service


def test_get_emails_public_read():
    """GET /emails — Public Read, без авторизации."""
    mock_service = make_mock_user_email_service()
    mock_service.get_user_emails.return_value = [
        {"id": str(uuid4()), "user_id": str(uuid4()), "email": "test@example.com", "approved": True}
    ]

    app.dependency_overrides[get_user_email_service] = lambda: mock_service

    try:
        response = TestClient(app).get("/emails?user_ids=" + str(uuid4()))
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    finally:
        app.dependency_overrides.clear()


def test_create_email_requires_auth():
    """POST /emails — Protected, без auth → 403."""
    response = TestClient(app).post("/emails", json={"user_id": str(uuid4()), "email": "test@example.com"})
    assert response.status_code in (401, 403)


def test_patch_email_requires_auth():
    """PATCH /emails — Protected, без auth → 403."""
    response = TestClient(app).patch("/emails", json={"user_id": str(uuid4()), "email": "test@example.com"})
    assert response.status_code in (401, 403)


def test_delete_email_requires_auth():
    """DELETE /emails/{user_id} — Protected, без auth → 403."""
    response = TestClient(app).delete(f"/emails/{uuid4()}")
    assert response.status_code in (401, 403)


def test_confirm_email_requires_auth():
    """PATCH /emails/confirm — Protected, без auth → 403."""
    response = TestClient(app).patch("/emails/confirm", json={"code": "test"})
    assert response.status_code in (401, 403)


def test_send_confirmation_requires_auth():
    """POST /emails/send-confirmation — Protected, без auth → 403."""
    response = TestClient(app).post("/emails/send-confirmation", json={"user_id": str(uuid4())})
    assert response.status_code in (401, 403)
