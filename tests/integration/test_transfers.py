import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.models import Account, Entry


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


def _fund_account(db_session: Session, *, account_id: int, amount: int) -> None:
    """Directly append a ledger entry and bump the cached balance — mirrors
    app.main.seed_entry, used here instead of that endpoint since it's gated
    by ENABLE_TEST_ENDPOINTS (off by default outside the CI Newman stage; see
    docs/test-pipeline-design.md).
    """
    account = db_session.get(Account, account_id)
    assert account is not None
    account.balance += amount
    db_session.add(Entry(account_id=account_id, amount=amount))
    db_session.add(account)
    db_session.commit()


def _create_account(client: TestClient, login_body: dict[str, str], currency: str) -> int:
    response = client.post(
        "/accounts", json={"currency": currency}, headers=_auth_headers(login_body)
    )
    account_id: int = response.json()["id"]
    return account_id


@pytest.mark.integration
def test_transfer_success_debits_and_credits_and_returns_entries(
    client: TestClient, db_session: Session
) -> None:
    alice_login = _register_and_login(client, username="alice")
    bob_login = _register_and_login(client, username="bob")
    from_account_id = _create_account(client, alice_login, "USD")
    to_account_id = _create_account(client, bob_login, "USD")
    _fund_account(db_session, account_id=from_account_id, amount=100)

    response = client.post(
        "/transfers",
        json={
            "from_account_id": from_account_id,
            "to_account_id": to_account_id,
            "amount": 30,
            "currency": "USD",
        },
        headers=_auth_headers(alice_login),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["from_account"]["balance"] == 70
    assert body["to_account"]["balance"] == 30
    assert body["from_entry"]["amount"] == -30
    assert body["to_entry"]["amount"] == 30
    assert body["transfer"]["amount"] == 30


@pytest.mark.integration
def test_transfer_updates_persisted_balances(client: TestClient, db_session: Session) -> None:
    alice_login = _register_and_login(client, username="alice")
    bob_login = _register_and_login(client, username="bob")
    from_account_id = _create_account(client, alice_login, "USD")
    to_account_id = _create_account(client, bob_login, "USD")
    _fund_account(db_session, account_id=from_account_id, amount=100)

    client.post(
        "/transfers",
        json={
            "from_account_id": from_account_id,
            "to_account_id": to_account_id,
            "amount": 30,
            "currency": "USD",
        },
        headers=_auth_headers(alice_login),
    )

    db_session.expire_all()
    from_account = db_session.get(Account, from_account_id)
    to_account = db_session.get(Account, to_account_id)
    assert from_account is not None
    assert to_account is not None
    assert from_account.balance == 70
    assert to_account.balance == 30


@pytest.mark.integration
def test_transfer_without_auth_returns_401(client: TestClient) -> None:
    response = client.post(
        "/transfers",
        json={"from_account_id": 1, "to_account_id": 2, "amount": 10, "currency": "USD"},
    )
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


@pytest.mark.integration
def test_transfer_from_account_not_owned_by_caller_returns_403(
    client: TestClient, db_session: Session
) -> None:
    alice_login = _register_and_login(client, username="alice")
    bob_login = _register_and_login(client, username="bob")
    alice_account_id = _create_account(client, alice_login, "USD")
    bob_account_id = _create_account(client, bob_login, "USD")
    _fund_account(db_session, account_id=alice_account_id, amount=100)

    response = client.post(
        "/transfers",
        json={
            "from_account_id": alice_account_id,
            "to_account_id": bob_account_id,
            "amount": 10,
            "currency": "USD",
        },
        headers=_auth_headers(bob_login),
    )
    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"


@pytest.mark.integration
def test_transfer_missing_account_returns_404(client: TestClient) -> None:
    alice_login = _register_and_login(client, username="alice")
    account_id = _create_account(client, alice_login, "USD")

    response = client.post(
        "/transfers",
        json={
            "from_account_id": account_id,
            "to_account_id": 999,
            "amount": 10,
            "currency": "USD",
        },
        headers=_auth_headers(alice_login),
    )
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


@pytest.mark.integration
def test_transfer_currency_mismatch_returns_400(client: TestClient, db_session: Session) -> None:
    alice_login = _register_and_login(client, username="alice")
    bob_login = _register_and_login(client, username="bob")
    from_account_id = _create_account(client, alice_login, "USD")
    to_account_id = _create_account(client, bob_login, "EUR")
    _fund_account(db_session, account_id=from_account_id, amount=100)

    response = client.post(
        "/transfers",
        json={
            "from_account_id": from_account_id,
            "to_account_id": to_account_id,
            "amount": 10,
            "currency": "USD",
        },
        headers=_auth_headers(alice_login),
    )
    assert response.status_code == 400
    assert response.json()["error"] == "currency_mismatch"


@pytest.mark.integration
def test_transfer_insufficient_funds_returns_400(client: TestClient) -> None:
    alice_login = _register_and_login(client, username="alice")
    bob_login = _register_and_login(client, username="bob")
    from_account_id = _create_account(client, alice_login, "USD")
    to_account_id = _create_account(client, bob_login, "USD")

    response = client.post(
        "/transfers",
        json={
            "from_account_id": from_account_id,
            "to_account_id": to_account_id,
            "amount": 10,
            "currency": "USD",
        },
        headers=_auth_headers(alice_login),
    )
    assert response.status_code == 400
    assert response.json()["error"] == "insufficient_funds"


@pytest.mark.integration
def test_transfer_non_positive_amount_returns_400_validation_error(client: TestClient) -> None:
    alice_login = _register_and_login(client, username="alice")
    bob_login = _register_and_login(client, username="bob")
    from_account_id = _create_account(client, alice_login, "USD")
    to_account_id = _create_account(client, bob_login, "USD")

    response = client.post(
        "/transfers",
        json={
            "from_account_id": from_account_id,
            "to_account_id": to_account_id,
            "amount": 0,
            "currency": "USD",
        },
        headers=_auth_headers(alice_login),
    )
    assert response.status_code == 400
    assert response.json()["error"] == "validation_error"
