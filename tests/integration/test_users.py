from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.models import Session as UserSession
from app.db.models import User


def _register_payload(**overrides: str) -> dict[str, str]:
    payload = {
        "username": "alice",
        "password": "secret123",
        "full_name": "Alice Anderson",
        "email": "alice@example.com",
    }
    payload.update(overrides)
    return payload


@pytest.mark.integration
def test_create_user_returns_201_without_password_fields(client: TestClient) -> None:
    response = client.post("/users", json=_register_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice"
    assert "password" not in body
    assert "hashed_password" not in body


@pytest.mark.integration
def test_create_user_persists_hashed_password(client: TestClient, db_session: Session) -> None:
    client.post("/users", json=_register_payload())
    user = db_session.exec(select(User).where(User.username == "alice")).first()
    assert user is not None
    assert user.hashed_password != "secret123"  # noqa: S105  # nosec B105 -- test fixture


@pytest.mark.integration
def test_create_user_duplicate_username_case_insensitive_returns_409(client: TestClient) -> None:
    client.post("/users", json=_register_payload())
    response = client.post(
        "/users", json=_register_payload(username="Alice", email="other@example.com")
    )
    assert response.status_code == 409
    assert response.json()["error"] == "duplicate_username"


@pytest.mark.integration
def test_create_user_duplicate_email_returns_409(client: TestClient) -> None:
    client.post("/users", json=_register_payload())
    response = client.post("/users", json=_register_payload(username="alice2"))
    assert response.status_code == 409
    assert response.json()["error"] == "duplicate_email"


@pytest.mark.integration
def test_create_user_missing_field_returns_400_validation_error(client: TestClient) -> None:
    payload = _register_payload()
    del payload["email"]
    response = client.post("/users", json=payload)
    assert response.status_code == 400
    assert response.json()["error"] == "validation_error"


@pytest.mark.integration
def test_create_user_username_too_short_returns_400_validation_error(client: TestClient) -> None:
    response = client.post("/users", json=_register_payload(username="ab"))
    assert response.status_code == 400
    assert response.json()["error"] == "validation_error"


@pytest.mark.integration
def test_login_success_returns_tokens_and_creates_session_row(
    client: TestClient, db_session: Session
) -> None:
    client.post("/users", json=_register_payload())
    response = client.post("/users/login", json={"username": "alice", "password": "secret123"})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["username"] == "alice"

    session_row = db_session.get(UserSession, UUID(body["session_id"]))
    assert session_row is not None


@pytest.mark.integration
def test_login_wrong_password_returns_401_invalid_credentials(client: TestClient) -> None:
    client.post("/users", json=_register_payload())
    response = client.post("/users/login", json={"username": "alice", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_credentials"


@pytest.mark.integration
def test_login_unknown_username_returns_401_invalid_credentials(client: TestClient) -> None:
    response = client.post("/users/login", json={"username": "nobody", "password": "secret123"})
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_credentials"
