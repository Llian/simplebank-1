from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.errors import DuplicateAccountError, ForbiddenError, NotFoundError
from app.db.models import Account, Currency
from app.services.account_service import AccountService


def _make_account(*, id: int, owner: str, currency: Currency, balance: int = 0) -> Account:
    return Account(
        id=id, owner=owner, balance=balance, currency=currency, created_at=datetime.now(UTC)
    )


class FakeAccountRepository:
    """Fake with a pre-populated `accounts` table and a create() that can be
    made to raise IntegrityError, to simulate a duplicate-check race — mirrors
    tests/unit/test_user_service.py's FakeUserRepository.
    """

    def __init__(self, existing: list[Account] | None = None) -> None:
        self.accounts: list[Account] = list(existing or [])
        self.raise_integrity_error_on_create = False
        self.get_by_owner_and_currency_call_count = 0
        self.miss_first_get_by_owner_and_currency_call = False

    def get(self, account_id: int) -> Account | None:
        return next((a for a in self.accounts if a.id == account_id), None)

    def get_by_owner_and_currency(self, *, owner: str, currency: Currency) -> Account | None:
        self.get_by_owner_and_currency_call_count += 1
        if (
            self.miss_first_get_by_owner_and_currency_call
            and self.get_by_owner_and_currency_call_count == 1
        ):
            return None
        return next((a for a in self.accounts if a.owner == owner and a.currency == currency), None)

    def list_by_owner(self, *, owner: str, page_id: int, page_size: int) -> list[Account]:
        matches = [a for a in self.accounts if a.owner == owner]
        start = (page_id - 1) * page_size
        return matches[start : start + page_size]

    def create(self, *, owner: str, currency: Currency) -> Account:
        if self.raise_integrity_error_on_create:
            raise IntegrityError("insert", {}, Exception("unique constraint"))
        account = _make_account(id=len(self.accounts) + 1, owner=owner, currency=currency)
        self.accounts.append(account)
        return account


@pytest.mark.unit
def test_create_account_success() -> None:
    service = AccountService(FakeAccountRepository())  # type: ignore[arg-type]
    account = service.create_account(owner="alice", currency=Currency.USD)
    assert account.owner == "alice"
    assert account.currency == Currency.USD


@pytest.mark.unit
def test_create_account_duplicate_currency_raises() -> None:
    repo = FakeAccountRepository(
        existing=[_make_account(id=1, owner="alice", currency=Currency.USD)]
    )
    service = AccountService(repo)  # type: ignore[arg-type]
    with pytest.raises(DuplicateAccountError):
        service.create_account(owner="alice", currency=Currency.USD)


@pytest.mark.unit
def test_create_account_same_owner_different_currency_succeeds() -> None:
    repo = FakeAccountRepository(
        existing=[_make_account(id=1, owner="alice", currency=Currency.USD)]
    )
    service = AccountService(repo)  # type: ignore[arg-type]
    account = service.create_account(owner="alice", currency=Currency.EUR)
    assert account.currency == Currency.EUR


@pytest.mark.unit
def test_create_account_integrity_error_race_resolves_to_duplicate() -> None:
    repo = FakeAccountRepository(
        existing=[_make_account(id=1, owner="alice", currency=Currency.USD)]
    )
    repo.raise_integrity_error_on_create = True
    repo.miss_first_get_by_owner_and_currency_call = True
    service = AccountService(repo)  # type: ignore[arg-type]

    with pytest.raises(DuplicateAccountError):
        service.create_account(owner="alice", currency=Currency.USD)


@pytest.mark.unit
def test_get_account_not_found_raises() -> None:
    service = AccountService(FakeAccountRepository())  # type: ignore[arg-type]
    with pytest.raises(NotFoundError):
        service.get_account(account_id=999, caller_username="alice")


@pytest.mark.unit
def test_get_account_wrong_owner_raises_forbidden() -> None:
    repo = FakeAccountRepository(
        existing=[_make_account(id=1, owner="alice", currency=Currency.USD)]
    )
    service = AccountService(repo)  # type: ignore[arg-type]
    with pytest.raises(ForbiddenError):
        service.get_account(account_id=1, caller_username="bob")


@pytest.mark.unit
def test_get_account_owner_success() -> None:
    repo = FakeAccountRepository(
        existing=[_make_account(id=1, owner="alice", currency=Currency.USD)]
    )
    service = AccountService(repo)  # type: ignore[arg-type]
    account = service.get_account(account_id=1, caller_username="alice")
    assert account.id == 1


@pytest.mark.unit
def test_list_accounts_returns_only_owners_accounts() -> None:
    repo = FakeAccountRepository(
        existing=[
            _make_account(id=1, owner="alice", currency=Currency.USD),
            _make_account(id=2, owner="bob", currency=Currency.USD),
            _make_account(id=3, owner="alice", currency=Currency.EUR),
        ]
    )
    service = AccountService(repo)  # type: ignore[arg-type]
    accounts = service.list_accounts(owner="alice", page_id=1, page_size=10)
    assert {a.id for a in accounts} == {1, 3}
