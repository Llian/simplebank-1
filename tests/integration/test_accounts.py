import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.models import Account


def _register_and_login(client: TestClient, *, username: str = "alice") -> dict[str, str]:
    client.post(
        "/users",
        json={
            "username": username,
            "password": "secret123",
            "full_name": "Full Name",
            "email": f"{username}@example.com",
        },
    )
    response = client.post("/users/login", json={"username": username, "password": "secret123"})
    body: dict[str, str] = response.json()
    return body


def _auth_headers(login_body: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {login_body['access_token']}"}


@pytest.mark.integration
def test_create_account_returns_201(client: TestClient) -> None:
    login_body = _register_and_login(client)
    response = client.post(
        "/accounts", json={"currency": "USD"}, headers=_auth_headers(login_body)
    )
    assert response.status_code == 201
    body = response.json()
    assert body["owner"] == "alice"
    assert body["currency"] == "USD"
    assert body["balance"] == 0


@pytest.mark.integration
def test_create_account_without_auth_returns_401(client: TestClient) -> None:
    response = client.post("/accounts", json={"currency": "USD"})
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


@pytest.mark.integration
def test_create_account_invalid_currency_returns_400_validation_error(
    client: TestClient,
) -> None:
    login_body = _register_and_login(client)
    response = client.post(
        "/accounts", json={"currency": "GBP"}, headers=_auth_headers(login_body)
    )
    assert response.status_code == 400
    assert response.json()["error"] == "validation_error"


@pytest.mark.integration
def test_create_duplicate_currency_account_returns_409(client: TestClient) -> None:
    login_body = _register_and_login(client)
    client.post("/accounts", json={"currency": "USD"}, headers=_auth_headers(login_body))
    response = client.post(
        "/accounts", json={"currency": "USD"}, headers=_auth_headers(login_body)
    )
    assert response.status_code == 409
    assert response.json()["error"] == "duplicate_account"


@pytest.mark.integration
def test_get_own_account_returns_200(client: TestClient) -> None:
    login_body = _register_and_login(client)
    create_response = client.post(
        "/accounts", json={"currency": "USD"}, headers=_auth_headers(login_body)
    )
    account_id = create_response.json()["id"]

    response = client.get(f"/accounts/{account_id}", headers=_auth_headers(login_body))
    assert response.status_code == 200
    assert response.json()["id"] == account_id


@pytest.mark.integration
def test_get_missing_account_returns_404(client: TestClient) -> None:
    login_body = _register_and_login(client)
    response = client.get("/accounts/999", headers=_auth_headers(login_body))
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


@pytest.mark.integration
def test_get_other_users_account_returns_403(client: TestClient) -> None:
    alice_login = _register_and_login(client, username="alice")
    bob_login = _register_and_login(client, username="bob")
    create_response = client.post(
        "/accounts", json={"currency": "USD"}, headers=_auth_headers(alice_login)
    )
    account_id = create_response.json()["id"]

    response = client.get(f"/accounts/{account_id}", headers=_auth_headers(bob_login))
    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"


@pytest.mark.integration
def test_list_accounts_returns_only_callers_accounts(
    client: TestClient, db_session: Session
) -> None:
    alice_login = _register_and_login(client, username="alice")
    bob_login = _register_and_login(client, username="bob")
    client.post("/accounts", json={"currency": "USD"}, headers=_auth_headers(alice_login))
    client.post("/accounts", json={"currency": "EUR"}, headers=_auth_headers(alice_login))
    client.post("/accounts", json={"currency": "USD"}, headers=_auth_headers(bob_login))

    response = client.get("/accounts", headers=_auth_headers(alice_login))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert {account["currency"] for account in body} == {"USD", "EUR"}


@pytest.mark.integration
def test_list_accounts_without_auth_returns_401(client: TestClient) -> None:
    response = client.get("/accounts")
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


@pytest.mark.integration
def test_account_creation_persists_row(client: TestClient, db_session: Session) -> None:
    login_body = _register_and_login(client)
    response = client.post(
        "/accounts", json={"currency": "USD"}, headers=_auth_headers(login_body)
    )
    account_id = response.json()["id"]
    account = db_session.get(Account, account_id)
    assert account is not None
    assert account.owner == "alice"
