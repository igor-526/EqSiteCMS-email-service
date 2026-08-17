"""Тесты API endpoints для email."""

from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from api.dependencies import get_user_email_service
from core.exceptions import ClientError, ConflictError, GoneError
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


def test_create_email_is_available_inside_private_network():
    service = make_mock_user_email_service()
    user_id = uuid4()
    service.create_email.return_value = {
        "id": str(uuid4()),
        "user_id": str(user_id),
        "email": "test@example.com",
        "approved": False,
    }
    app.dependency_overrides[get_user_email_service] = lambda: service
    try:
        response = TestClient(app).post("/emails", json={"user_id": str(user_id), "email": "test@example.com"})
        assert response.status_code == 201
    finally:
        app.dependency_overrides.clear()


def test_patch_email_is_available_inside_private_network():
    service = make_mock_user_email_service()
    user_id = uuid4()
    service.change_email.return_value = {
        "id": str(uuid4()),
        "user_id": str(user_id),
        "email": "test@example.com",
        "approved": False,
    }
    app.dependency_overrides[get_user_email_service] = lambda: service
    try:
        response = TestClient(app).patch("/emails", json={"user_id": str(user_id), "email": "test@example.com"})
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_delete_email_is_available_inside_private_network():
    service = make_mock_user_email_service()
    app.dependency_overrides[get_user_email_service] = lambda: service
    try:
        response = TestClient(app).delete(f"/emails/{uuid4()}")
        assert response.status_code == 204
    finally:
        app.dependency_overrides.clear()


def test_confirm_email_is_public():
    """PATCH /emails/confirm — public confirmation exception."""
    from api.dependencies import get_email_confirmation_service

    service = make_mock_confirmation_service()
    service.confirm.return_value = {"status": "confirmed", "user_email_id": str(uuid4())}
    app.dependency_overrides[get_email_confirmation_service] = lambda: service
    try:
        response = TestClient(app).patch("/emails/confirm", json={"code": "test"})
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_unknown_confirmation_code_is_400():
    """A well-formed but unknown code is an invalid request, not a missing resource."""
    from api.dependencies import get_email_confirmation_service

    service = make_mock_confirmation_service()
    service.confirm.side_effect = ClientError("Confirmation code is invalid")
    app.dependency_overrides[get_email_confirmation_service] = lambda: service
    try:
        response = TestClient(app).patch("/emails/confirm", json={"code": "unknown-code"})
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_reused_confirmation_code_remains_409():
    from api.dependencies import get_email_confirmation_service

    service = make_mock_confirmation_service()
    service.confirm.side_effect = ConflictError("Confirmation link already used")
    app.dependency_overrides[get_email_confirmation_service] = lambda: service
    try:
        response = TestClient(app).patch("/emails/confirm", json={"code": "reused-code"})
        assert response.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_expired_confirmation_code_remains_410():
    from api.dependencies import get_email_confirmation_service

    service = make_mock_confirmation_service()
    service.confirm.side_effect = GoneError("Confirmation link expired")
    app.dependency_overrides[get_email_confirmation_service] = lambda: service
    try:
        response = TestClient(app).patch("/emails/confirm", json={"code": "expired-code"})
        assert response.status_code == 410
    finally:
        app.dependency_overrides.clear()


def test_send_confirmation_is_public(monkeypatch):
    """POST /emails/send-confirmation — public confirmation exception."""
    service = make_mock_user_email_service()
    service.get_user_email.return_value = {"id": uuid4(), "email": "test@example.com"}
    app.dependency_overrides[get_user_email_service] = lambda: service

    class FakeTask:
        @staticmethod
        def delay(_: str) -> None:
            return None

    monkeypatch.setattr("workers.tasks.confirmation.send_confirmation_email_task", FakeTask())
    try:
        response = TestClient(app).post("/emails/send-confirmation", json={"user_id": str(uuid4())})
        assert response.status_code == 202
    finally:
        app.dependency_overrides.clear()


def test_invalid_email_is_400():
    service = make_mock_user_email_service()
    app.dependency_overrides[get_user_email_service] = lambda: service
    try:
        response = TestClient(app).post("/emails", json={"user_id": str(uuid4()), "email": "invalid"})
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()
