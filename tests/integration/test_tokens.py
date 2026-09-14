from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.models import Session as UserSession


def _register_and_login(client: TestClient) -> dict[str, str]:
    client.post(
        "/users",
        json={
            "username": "alice",
            "password": "secret123",
            "full_name": "Alice Anderson",
            "email": "alice@example.com",
        },
    )
    response = client.post("/users/login", json={"username": "alice", "password": "secret123"})
    body: dict[str, str] = response.json()
    return body


@pytest.mark.integration
def test_renew_access_success_returns_new_access_token(client: TestClient) -> None:
    login_body = _register_and_login(client)
    response = client.post(
        "/tokens/renew_access", json={"refresh_token": login_body["refresh_token"]}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


@pytest.mark.integration
def test_renew_access_garbage_token_returns_401_unauthorized(client: TestClient) -> None:
    response = client.post("/tokens/renew_access", json={"refresh_token": "not-a-jwt"})
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


@pytest.mark.integration
def test_renew_access_blocked_session_returns_401_unauthorized(
    client: TestClient, db_session: Session
) -> None:
    login_body = _register_and_login(client)
    session_row = db_session.get(UserSession, UUID(login_body["session_id"]))
    assert session_row is not None
    session_row.is_blocked = True
    db_session.add(session_row)
    db_session.commit()

    response = client.post(
        "/tokens/renew_access", json={"refresh_token": login_body["refresh_token"]}
    )
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


@pytest.mark.integration
def test_renew_access_expired_session_row_returns_401_unauthorized(
    client: TestClient, db_session: Session
) -> None:
    login_body = _register_and_login(client)
    session_row = db_session.get(UserSession, UUID(login_body["session_id"]))
    assert session_row is not None
    session_row.expires_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.add(session_row)
    db_session.commit()

    response = client.post(
        "/tokens/renew_access", json={"refresh_token": login_body["refresh_token"]}
    )
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


@pytest.mark.integration
def test_renew_access_mismatched_stored_token_returns_401_unauthorized(
    client: TestClient, db_session: Session
) -> None:
    login_body = _register_and_login(client)
    session_row = db_session.get(UserSession, UUID(login_body["session_id"]))
    assert session_row is not None
    session_row.refresh_token = "a-different-token"  # noqa: S105  # nosec B105 -- test fixture
    db_session.add(session_row)
    db_session.commit()

    response = client.post(
        "/tokens/renew_access", json={"refresh_token": login_body["refresh_token"]}
    )
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"
